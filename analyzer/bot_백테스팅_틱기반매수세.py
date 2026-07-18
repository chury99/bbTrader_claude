import os
import sys
import re

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

import ut

# 매수세 전략 파라미터 (환경변수로 조정 가능)
# 진입 (분석 근거: 눌림 5%+ 구간에서만 신호 지속, 강도-수익 단조 관계)
_T_순매수비율 = float(os.environ.get('TB_RATIO', '0.4'))      # 60초 순매수비율 임계값 (매수세 형성)
_T_거래강도 = float(os.environ.get('TB_INT', '5.0'))          # 직전 5분 대비 60초 거래량 배수
_T_이격최소 = float(os.environ.get('TB_DIST', '5.0'))         # 당일고가 대비 최소 이격 % (눌림 필터)
_T_일최대거래 = int(os.environ.get('TB_MAXPERDAY', '2'))       # 종목당 1일 최대 진입 횟수
_T_쿨다운 = int(os.environ.get('TB_COOLDOWN', '600'))         # 청산 후 재진입 대기 (초)
# 청산
_T_손절 = float(os.environ.get('TB_STOP', '2.0'))            # 손절 % (매수가 대비)
_T_최소보유 = int(os.environ.get('TB_MINHOLD', '600'))        # 최소 보유시간 (초) - 이 동안은 손절만 작동 (신호 유효시간 ~10분에 맞춤)
# 공통
_T_비용 = float(os.environ.get('TB_COST', '0.35'))           # 왕복 거래비용 % (수수료+세금+슬리피지)
_T_차트최대 = int(os.environ.get('TB_CHARTMAX', '30'))        # 매매일보 개별 거래차트 최대 수
# 종목선정 (전일 일봉 기준)
_T_최소거래대금 = float(os.environ.get('TB_MINVALUE', '5000'))  # 전일 거래대금 하한 (백만원, 5000=50억)
_T_최소가격 = float(os.environ.get('TB_MINPRICE', '1000'))     # 전일 종가 하한 (원, 저가주 제외)
# 자금관리 (실시간매매 bot_실시간매매와 동일한 리스크 기반 사이징)
_T_초기예수금 = int(os.environ.get('TB_INITCASH', '10000000'))  # 백테스팅 시작 예수금 (원, 실매매는 계좌 조회)
_T_투입비율 = float(os.environ.get('TB_CHUNK_PCT', '50.0'))     # 진입 시 남은 예수금 중 투입 비율 % (2덩어리 분할=50%)
_T_리스크비율 = float(os.environ.get('TB_RISK_PCT', '2.0'))     # 덩어리 대비 감내 리스크 예산 % (손절 시 최대 손실, TB_STOP과 별개)


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker,PyAttributeOutsideInit
class AnalyzerBot:
    """ 틱 데이터 기반 매수세 전략 백테스팅 (벡터연산, 독립 동작)
        파이프라인: pick_종목선정 → make_매매정보 → make_거래내역 → make_결과정리 → make_매매일보
        - 진입: 매수세 형성 (60초 순매수비율/거래강도) + 눌림(고가 대비 이격) 필터
        - 청산: 매수세 소멸 (최소보유 이후) / 손절 / 장마감 """

    # noinspection PyUnresolvedReferences
    def __init__(self, n_검증일수=60, b_디버그모드=False):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_analyzer')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보
        self.folder_백테스팅 = os.path.join(dic_폴더정보['분석|백테스팅'], '클로드_틱기반매수세')
        os.makedirs(self.folder_백테스팅, exist_ok=True)
        self.folder_틱 = dic_폴더정보['매수매도|주식체결']
        self.folder_감시종목 = dic_폴더정보['매수매도|감시종목']

        # 추가 폴더 정의 - 일봉 캐시 (차트/종목선정용)
        self.folder_서버 = ('/Volumes/extSSD4tb/80_Backup/10_python_backup/ProjectWork/spTraderV2'
                          if sys.platform == 'darwin' else '')

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.n_검증일수 = n_검증일수
        self.b_디버그모드 = b_디버그모드
        self.s_틱시작일 = '20260716'    # 틱 데이터 유효 시작일 (일 전체 수집 시작일)
        self.n_장마감초 = 15 * 3600 + 15 * 60    # 15:15 강제청산

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()
        self.chart = ut.차트maker.ChartMaker()

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    # -----------------------------------------------------------------
    def _li_대상일자(self, folder_타겟, file_타겟):
        """ 처리 대상일자 산출 (틱시작일 이후, 완료 제외, 당일 장중 제외) """
        s_지금 = pd.Timestamp.now()
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(self.folder_틱)
                         if '주식체결_' in 파일 and '.csv' in 파일)
        li_전체일자 = [일자 for 일자 in li_전체일자 if 일자 >= self.s_틱시작일]
        if s_지금.strftime('%H%M') < '1535':
            li_전체일자 = [일자 for 일자 in li_전체일자 if 일자 != s_지금.strftime('%Y%m%d')]
        li_완료일자 = ([re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                    if file_타겟 in 파일 and '.pkl' in 파일] if os.path.exists(folder_타겟) else list())
        return [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

    # -----------------------------------------------------------------
    def pick_종목선정(self):
        """ 감시종목 중 전일 일봉 기준으로 매매 대상 선정 (유동성/가격 필터) """
        # 기준정보 정의
        folder_타겟 = os.path.join(self.folder_백테스팅, '10_종목선정')
        file_타겟 = f'df_종목선정'
        os.makedirs(folder_타겟, exist_ok=True)

        # 일자별 종목선정
        for s_일자 in self._li_대상일자(folder_타겟=folder_타겟, file_타겟=file_타겟):
            # 감시종목 불러오기 (해당일 등록 목록, 없으면 틱 파일에서 추출)
            path_감시 = os.path.join(self.folder_감시종목, f'dic_감시종목_{s_일자}.pkl')
            if os.path.exists(path_감시):
                dic_감시종목 = pd.read_pickle(path_감시)
                li_감시종목 = dic_감시종목.get('매매대상', list()) + dic_감시종목.get('수집대상', list())
            else:
                df_틱헤더 = pd.read_csv(os.path.join(self.folder_틱, f'주식체결_{s_일자}.csv'),
                                     encoding='cp949', usecols=['종목코드'], dtype=str, on_bad_lines='skip')
                li_감시종목 = df_틱헤더['종목코드'].str.strip().unique().tolist()

            # 전일 일봉 지표 확인
            dic_종목명, dic_전일고가 = self._load_일봉맵(s_일자=s_일자)
            dic_일봉 = self._load_일봉캐시(s_일자=s_일자, b_전일=True)
            li_dic선정 = list()
            for s_종목코드 in li_감시종목:
                df_일봉 = dic_일봉.get(s_종목코드, None)
                if df_일봉 is None or len(df_일봉) == 0:
                    continue
                sri_전일 = df_일봉.iloc[-1]
                n_전일종가 = sri_전일['종가']
                n_전일거래대금 = sri_전일['거래대금(백만)']
                b_선정 = (n_전일거래대금 >= _T_최소거래대금) and (n_전일종가 >= _T_최소가격)
                li_dic선정.append(dict(종목코드=s_종목코드, 종목명=dic_종목명.get(s_종목코드, s_종목코드),
                                     전일종가=n_전일종가, 전일거래대금=n_전일거래대금,
                                     전일고가=dic_전일고가.get(s_종목코드, np.nan), 종목선정=b_선정))

            # 저장
            df_종목선정 = pd.DataFrame(li_dic선정)
            self.tool.df저장(df=df_종목선정, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_선정 = int(df_종목선정['종목선정'].sum()) if len(df_종목선정) > 0 else 0
            self.make_로그(f'{s_일자} - 감시 {len(li_감시종목)}개 중 {n_선정}개 선정')

    # -----------------------------------------------------------------
    def make_매매정보(self):
        """ 선정 종목의 틱 데이터에서 매수세 신호 기반 매매정보 생성 (벡터연산) + 3분봉 캐시 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '10_종목선정')
        folder_타겟 = os.path.join(self.folder_백테스팅, '20_매매정보')
        file_타겟 = f'dic_매매정보'
        os.makedirs(folder_타겟, exist_ok=True)

        # 일자별 처리
        for s_일자 in self._li_대상일자(folder_타겟=folder_타겟, file_타겟=file_타겟):
            # 종목선정 불러오기
            path_선정 = os.path.join(folder_소스, f'df_종목선정_{s_일자}.pkl')
            if not os.path.exists(path_선정):
                continue
            df_종목선정 = pd.read_pickle(path_선정)
            if df_종목선정.empty:
                continue
            df_종목선정 = df_종목선정.set_index('종목코드', drop=False)
            li_대상종목 = df_종목선정.loc[df_종목선정['종목선정']]['종목코드'].tolist()

            # 틱 데이터 로딩 (벡터 파싱)
            df_틱 = self._load_틱(s_일자=s_일자)
            if df_틱 is None or len(df_틱) == 0:
                self.make_로그(f'{s_일자} - 틱 데이터 없음')
                continue

            # 3분봉 캐시 생성 (차트용, 전체 수신종목 대상)
            dic_종목명 = df_종목선정['종목명'].to_dict()
            self._make_3분봉캐시(df_틱=df_틱, s_일자=s_일자, dic_종목명=dic_종목명)

            # 종목별 매매정보(거래 시뮬) 생성 - 선정 종목만
            dic_매매정보 = dict()
            df_틱대상 = df_틱[df_틱['종목코드'].isin(li_대상종목)]
            for s_종목코드, df_종목 in df_틱대상.groupby('종목코드', sort=False):
                df_거래 = self._make_거래_종목(
                    df_종목=df_종목, s_일자=s_일자, s_종목코드=s_종목코드,
                    s_종목명=df_종목선정.loc[s_종목코드, '종목명'],
                    n_전일고가=df_종목선정.loc[s_종목코드, '전일고가'])
                if len(df_거래) > 0:
                    dic_매매정보[s_종목코드] = df_거래

            # 저장
            pd.to_pickle(dic_매매정보, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 로그 기록
            n_거래 = sum(len(df) for df in dic_매매정보.values())
            self.make_로그(f'{s_일자} - {len(li_대상종목)}종목 중 {len(dic_매매정보)}종목 거래, {n_거래}건')

    # -----------------------------------------------------------------
    def make_거래내역(self):
        """ 매매정보를 바탕으로 거래내역 정리 (기존 파이프라인과 동일 포맷) """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '20_매매정보')
        file_소스 = f'dic_매매정보'
        folder_타겟 = os.path.join(self.folder_백테스팅, '30_거래내역')
        file_타겟 = f'df_거래내역'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 거래내역 정리
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            dic_매매정보 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # 거래내역 생성
            li_df거래 = [df for df in dic_매매정보.values() if df is not None and len(df) > 0]
            df_거래내역 = (pd.concat(li_df거래).sort_values('매수시점').reset_index(drop=True)
                       if len(li_df거래) > 0 else pd.DataFrame())

            # 저장
            self.tool.df저장(df=df_거래내역, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 지표 로그 (기존 포맷)
            n_총 = len(df_거래내역)
            if n_총 > 0:
                sri_수익 = df_거래내역['수익률']
                n_승 = int((sri_수익 > 0).sum())
                n_승률 = n_승 / n_총 * 100
                n_평수 = sri_수익[sri_수익 > 0].mean() if n_승 > 0 else 0
                n_평손 = sri_수익[sri_수익 <= 0].mean() if n_총 - n_승 > 0 else 0
                n_손익비 = n_평수 / abs(n_평손) if n_평손 != 0 else 0
                n_기대치 = (n_승률 / 100 * n_손익비) - (1 - n_승률 / 100)
                self.make_로그(f'{s_일자}\n'
                             f' - 기대치 {n_기대치:,.2f}, 총수익 {sri_수익.sum():,.1f}%\n'
                             f' - 승률 {n_승률:,.0f}% (총 {n_총}, 승 {n_승}, 패 {n_총 - n_승})\n'
                             f' - 손익비 {n_손익비:,.1f} (평균수익 {n_평수:,.2f}%, 평균손실 {n_평손:,.2f}%)')
            else:
                self.make_로그(f'{s_일자} - 거래 없음')

    # -----------------------------------------------------------------
    def make_결과정리(self):
        """ 검증기간 동안의 전체 결과 정리 (기존 파이프라인과 동일 포맷) """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '30_거래내역')
        file_소스 = f'df_거래내역'
        folder_타겟 = os.path.join(self.folder_백테스팅, '40_결과정리')
        file_타겟 = f'df_결과정리'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 결과정리 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            li_파일일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스) if '.pkl' in 파일]
            li_파일일자 = [일자 for 일자 in li_파일일자 if 일자 <= s_일자]

            # 결과정리
            li_dic결과정리 = list()
            li_df누적거래 = list()
            for s_파일일자 in sorted(li_파일일자):
                # 기준정보 정의
                df_거래내역 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_파일일자}.pkl'))

                # 지표 생성
                df_손익정리_수익 = df_거래내역.loc[df_거래내역['수익률'] > 0] if not df_거래내역.empty else pd.DataFrame()
                df_손익정리_손실 = df_거래내역.loc[df_거래내역['수익률'] <= 0] if not df_거래내역.empty else pd.DataFrame()
                n_일간매매 = len(df_거래내역)
                n_일간수익매매 = len(df_손익정리_수익)
                n_일간손실매매 = len(df_손익정리_손실)
                n_일간승률 = n_일간수익매매 / n_일간매매 * 100 if n_일간매매 > 0 else 0
                n_일간총손익 = df_거래내역['수익률'].sum() if n_일간매매 > 0 else 0
                n_일간평균수익 = df_손익정리_수익['수익률'].mean() if n_일간수익매매 > 0 else 0
                n_일간평균손실 = df_손익정리_손실['수익률'].mean() if n_일간손실매매 > 0 else 0
                n_일간손익비 = n_일간평균수익 / abs(n_일간평균손실) if n_일간평균손실 != 0 else 0
                n_일간기대치 = (n_일간승률 / 100 * n_일간손익비) - (1 - n_일간승률 / 100) if n_일간매매 > 0 else 0

                # 결과 생성
                dic_결과정리 = dict(일자=s_파일일자,
                                일간매매=n_일간매매, 일간수익매매=n_일간수익매매, 일간손실매매=n_일간손실매매, 일간승률=n_일간승률,
                                일간총손익=n_일간총손익, 일간평균수익=n_일간평균수익, 일간평균손실=n_일간평균손실,
                                일간손익비=n_일간손익비, 일간기대치=n_일간기대치)
                li_dic결과정리.append(dic_결과정리)
                li_df누적거래.append(df_거래내역)

            # df 생성
            df_결과정리 = pd.DataFrame(li_dic결과정리).sort_values('일자') if len(li_dic결과정리) > 0 else pd.DataFrame()
            df_누적거래 = (pd.concat(li_df누적거래).sort_values(['일자', '매수시점']) if len(li_df누적거래) > 0
                       and sum(len(df) for df in li_df누적거래) > 0 else pd.DataFrame())

            # 예수금 기반 리스크 사이징 시뮬레이션 (실시간매매와 동일 규칙, 일자 이월=복리)
            df_누적거래, dic_종료예수금 = self._simulate_예수금(df_누적거래)
            if not df_결과정리.empty:
                df_결과정리['거래후예수금'] = (df_결과정리['일자'].map(dic_종료예수금)
                                        .ffill().fillna(_T_초기예수금).astype('int64'))

            # 데이터 저장
            self.tool.df저장(df=df_결과정리, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))
            os.makedirs(folder := f'{folder_타겟}_누적거래', exist_ok=True)
            self.tool.df저장(df=df_누적거래, path=os.path.join(folder, f'df_누적거래_{s_일자}'))

            # 지표 정의
            df_누적거래_수익 = df_누적거래.loc[df_누적거래['수익률'] > 0] if len(df_누적거래) > 0 else pd.DataFrame()
            df_누적거래_손실 = df_누적거래.loc[df_누적거래['수익률'] <= 0] if len(df_누적거래) > 0 else pd.DataFrame()
            n_누적매매 = len(df_누적거래)
            n_누적수익매매 = len(df_누적거래_수익)
            n_누적손실매매 = len(df_누적거래_손실)
            n_누적승률 = n_누적수익매매 / n_누적매매 * 100 if n_누적매매 > 0 else 0
            n_누적총손익 = df_누적거래['수익률'].sum() if n_누적매매 > 0 else 0
            n_누적평균수익 = df_누적거래_수익['수익률'].mean() if n_누적수익매매 > 0 else 0
            n_누적평균손실 = df_누적거래_손실['수익률'].mean() if n_누적손실매매 > 0 else 0
            n_누적손익비 = n_누적평균수익 / abs(n_누적평균손실) if n_누적평균손실 != 0 else 0
            n_누적기대치 = (n_누적승률 / 100 * n_누적손익비) - (1 - n_누적승률 / 100) if n_누적매매 > 0 else 0

            # 로그 기록
            n_누적일수 = len(df_결과정리)
            self.make_로그(f'{s_일자}({n_누적일수}일)\n'
                         f' - 누적기대치 {n_누적기대치:,.2f}, 누적수익 {n_누적총손익:,.0f}%\n'
                         f' - 누적승률 {n_누적승률:,.0f}% (총 {n_누적매매}, 승 {n_누적수익매매}, 패 {n_누적손실매매})\n'
                         f' - 누적손익비 {n_누적손익비:,.1f} (평균수익 {n_누적평균수익:,.0f}%, 평균손실 {n_누적평균손실:,.0f}%)')

    # -----------------------------------------------------------------
    def _simulate_예수금(self, df_누적거래):
        """ 전체 거래를 시간순 재생하여 예수금 기반 리스크 사이징 적용 (실시간매매 bot_실시간매매와 동일 규칙)
            - 덩어리 = 예수금 × 투입비율%(50%)          : 진입마다 남은 예수금의 절반
            - 매수금액 = 덩어리 × (리스크비율 / 손절률)  : 손절 시 손실이 리스크예산(덩어리×2%) 이내
            - 예수금은 일자를 넘어 이월(복리). 청산 시 원금+손익 회수 후 다음 진입 사이징에 반영
            - 당일 전량청산(오버나이트 없음) 전제 → 일자별 종료예수금 = 초기예수금 + 누적손익금
            반환: (수량/매수금액/손익금/진입후예수금 컬럼 추가 df, {일자: 종료예수금}) """
        if df_누적거래.empty:
            return df_누적거래, dict()
        df = df_누적거래.sort_values(['일자', '매수시점']).reset_index(drop=True).copy()
        n = len(df)
        ary_일자 = df['일자'].astype(str).values
        ary_매수시점 = df['매수시점'].astype(str).values
        ary_매도시점 = df['매도시점'].astype(str).values
        ary_매수가 = df['매수가'].astype(float).values
        ary_수익률 = df['수익률'].astype(float).values

        ary_수량 = np.zeros(n, dtype='int64')
        ary_매수금액 = np.zeros(n, dtype='int64')
        ary_손익금 = np.zeros(n, dtype='int64')
        ary_진입후예수금 = np.zeros(n, dtype='int64')

        n_예수금 = float(_T_초기예수금)
        n_배수 = (_T_리스크비율 / _T_손절) if _T_손절 > 0 else 1.0
        li_오픈 = list()   # (정산키='일자+매도시각', 실매수금액, 수익률)

        for i in range(n):
            s_진입키 = ary_일자[i] + ary_매수시점[i]
            # 이 진입 이전에 청산된 포지션 회수 (원금 + 손익, 문자열키가 시간순 정렬)
            li_잔여 = list()
            for s_청산키, n_금액, n_ret in li_오픈:
                if s_청산키 <= s_진입키:
                    n_예수금 += n_금액 * (1 + n_ret / 100)
                else:
                    li_잔여.append((s_청산키, n_금액, n_ret))
            li_오픈 = li_잔여

            # 리스크 사이징
            n_매수가 = ary_매수가[i]
            n_목표금액 = n_예수금 * _T_투입비율 / 100 * n_배수
            n_수량 = int(n_목표금액 // n_매수가) if n_매수가 > 0 else 0
            if n_수량 * n_매수가 > n_예수금:                    # 예수금 한도 초과 방지
                n_수량 = int(n_예수금 // n_매수가) if n_매수가 > 0 else 0
            if n_수량 <= 0:                                    # 예수금 부족 - 미체결
                ary_진입후예수금[i] = int(n_예수금)
                continue

            n_실매수금액 = n_수량 * n_매수가
            n_예수금 -= n_실매수금액
            li_오픈.append((ary_일자[i] + ary_매도시점[i], n_실매수금액, ary_수익률[i]))
            ary_수량[i] = n_수량
            ary_매수금액[i] = int(n_실매수금액)
            ary_손익금[i] = int(n_실매수금액 * ary_수익률[i] / 100)
            ary_진입후예수금[i] = int(n_예수금)

        df['수량'] = ary_수량
        df['매수금액'] = ary_매수금액
        df['손익금'] = ary_손익금
        df['진입후예수금'] = ary_진입후예수금   # 매수 직후 잔여 예수금 (참고용)

        # 일자별 종료예수금 = 초기예수금 + 누적손익금 (당일 원금 전량 회수 전제)
        sri_일손익 = df.groupby('일자')['손익금'].sum().sort_index()
        dic_종료예수금 = (_T_초기예수금 + sri_일손익.cumsum()).astype('int64').to_dict()
        return df, dic_종료예수금

    # -----------------------------------------------------------------
    def _load_틱(self, s_일자):
        """ 하루치 틱 CSV 로딩 및 벡터 전처리 """
        path_틱 = os.path.join(self.folder_틱, f'주식체결_{s_일자}.csv')
        if not os.path.exists(path_틱):
            return None
        li_사용컬럼 = ['종목코드', '체결시간', '현재가', '거래량', '고가']
        df = pd.read_csv(path_틱, encoding='cp949', usecols=li_사용컬럼, dtype=str, on_bad_lines='skip')

        # 벡터 변환 (부호 제거 - 거래량은 부호가 매수/매도 방향이므로 유지)
        for s_컬럼 in ['현재가', '고가']:
            df[s_컬럼] = pd.to_numeric(df[s_컬럼].str.replace('+', '', regex=False).str.replace('-', '', regex=False),
                                     errors='coerce')
        df['거래량'] = pd.to_numeric(df['거래량'], errors='coerce')
        df = df.dropna(subset=['현재가', '거래량', '고가'])
        df['종목코드'] = df['종목코드'].str.strip()

        # 초 단위 시간 (벡터)
        sri_시간 = df['체결시간'].str
        df['초'] = (pd.to_numeric(sri_시간[:2], errors='coerce') * 3600
                   + pd.to_numeric(sri_시간[2:4], errors='coerce') * 60
                   + pd.to_numeric(sri_시간[4:6], errors='coerce'))
        df = df.dropna(subset=['초'])
        df['초'] = df['초'].astype(int)
        df = df[(df['초'] >= 9 * 3600) & (df['초'] <= 15 * 3600 + 30 * 60)]

        return df

    # -----------------------------------------------------------------
    def _load_일봉캐시(self, s_일자, b_전일=False):
        """ 일봉 캐시 로딩 (b_전일=True 시 해당일 이전 최신 캐시) """
        folder_일봉 = os.path.join(self.folder_서버, '데이터', '차트캐시', '일봉1')
        s_조건 = (lambda 일자: 일자 < s_일자) if b_전일 else (lambda 일자: 일자 <= s_일자)
        li_파일 = sorted(파일 for 파일 in os.listdir(folder_일봉)
                       if '.pkl' in 파일 and s_조건(re.findall(r'\d{8}', 파일)[0]))
        return pd.read_pickle(os.path.join(folder_일봉, li_파일[-1])) if len(li_파일) > 0 else dict()

    def _load_일봉맵(self, s_일자):
        """ 일봉 캐시에서 종목명, 전일고가 매핑 로딩 """
        dic_일봉 = self._load_일봉캐시(s_일자=s_일자, b_전일=True)
        dic_종목명, dic_전일고가 = dict(), dict()
        for s_종목코드, df_일봉 in dic_일봉.items():
            if len(df_일봉) == 0:
                continue
            dic_종목명[s_종목코드] = df_일봉['종목명'].values[-1]
            dic_전일고가[s_종목코드] = df_일봉['고가'].values[-1]
        return dic_종목명, dic_전일고가

    # -----------------------------------------------------------------
    def _make_3분봉캐시(self, df_틱, s_일자, dic_종목명):
        """ 틱 데이터에서 3분봉 생성 (차트용, 벡터연산) """
        df = df_틱.copy()
        df['분3'] = (df['초'] // 180) * 180
        df['절대거래량'] = df['거래량'].abs()

        # OHLCV 집계 (벡터)
        df_3분봉 = (df.groupby(['종목코드', '분3'])
                    .agg(시가=('현재가', 'first'), 고가=('현재가', 'max'),
                         저가=('현재가', 'min'), 종가=('현재가', 'last'), 거래량=('절대거래량', 'sum'))
                    .reset_index())
        df_3분봉['일자'] = s_일자
        df_3분봉['종목명'] = df_3분봉['종목코드'].map(dic_종목명).fillna(df_3분봉['종목코드'])
        df_3분봉['시간'] = (df_3분봉['분3'] // 3600).astype(str).str.zfill(2) + ':' + \
                        (df_3분봉['분3'] % 3600 // 60).astype(str).str.zfill(2) + ':00'

        # 이동평균 (그룹 벡터연산)
        df_3분봉 = df_3분봉.sort_values(['종목코드', '분3'])
        gr = df_3분봉.groupby('종목코드')
        for n_기간 in [5, 10, 20, 60, 120]:
            df_3분봉[f'종가ma{n_기간}'] = gr['종가'].transform(lambda x: x.rolling(n_기간).mean())
        for n_기간 in [5, 20, 60, 120]:
            df_3분봉[f'거래량ma{n_기간}'] = gr['거래량'].transform(lambda x: x.rolling(n_기간).mean())

        # 캐시 저장 (매매일보 차트용)
        li_컬럼 = ['일자', '종목코드', '종목명', '시간', '시가', '고가', '저가', '종가', '거래량',
                 '종가ma5', '종가ma10', '종가ma20', '종가ma60', '종가ma120',
                 '거래량ma5', '거래량ma20', '거래량ma60', '거래량ma120']
        dic_3분봉 = {코드: df[li_컬럼].reset_index(drop=True) for 코드, df in df_3분봉.groupby('종목코드')}
        os.makedirs(folder := os.path.join(self.folder_백테스팅, '20_매매정보_3분봉'), exist_ok=True)
        pd.to_pickle(dic_3분봉, os.path.join(folder, f'dic_차트캐시_3분봉_{s_일자}.pkl'))

    # -----------------------------------------------------------------
    def _make_거래_종목(self, df_종목, s_일자, s_종목코드, s_종목명, n_전일고가):
        """ 종목 하나의 틱을 1초봉으로 집계 후 매수세 신호/거래 추출 (벡터연산 + 거래 단위 루프) """
        if len(df_종목) < 500:
            return pd.DataFrame()

        # 1초봉 집계 (벡터)
        df_매수 = df_종목.loc[df_종목['거래량'] > 0].groupby('초')['거래량'].sum()
        df_매도 = -df_종목.loc[df_종목['거래량'] < 0].groupby('초')['거래량'].sum()
        sri_가격 = df_종목.groupby('초')['현재가'].last()
        sri_당일고가 = df_종목.groupby('초')['고가'].last()

        # 연속 초 인덱스 리샘플 (벡터)
        ary_초 = np.arange(sri_가격.index.min(), sri_가격.index.max() + 1)
        df_1초 = pd.DataFrame(index=ary_초)
        df_1초['price'] = sri_가격.reindex(ary_초).ffill()
        df_1초['high'] = sri_당일고가.reindex(ary_초).ffill()
        df_1초['매수량'] = df_매수.reindex(ary_초).fillna(0)
        df_1초['매도량'] = df_매도.reindex(ary_초).fillna(0)

        # 매수세 지표 (벡터 rolling)
        sri_전체 = df_1초['매수량'] + df_1초['매도량']
        sri_순매수60 = (df_1초['매수량'] - df_1초['매도량']).rolling(60).sum()
        sri_전체60 = sri_전체.rolling(60).sum()
        df_1초['순매수비율'] = sri_순매수60 / sri_전체60.replace(0, np.nan)
        sri_기준거래량 = sri_전체.rolling(300).sum().shift(60) / 5
        df_1초['거래강도'] = sri_전체60 / sri_기준거래량.replace(0, np.nan)
        df_1초['이격률'] = (df_1초['high'].shift(1) - df_1초['price']) / df_1초['high'].shift(1) * 100
        df_1초['변동폭300'] = df_1초['price'].rolling(300).max() - df_1초['price'].rolling(300).min()

        # 신호 마스크 (벡터)
        n_웜업 = ary_초[0] + 360
        ary_진입 = ((df_1초['순매수비율'] > _T_순매수비율) & (df_1초['거래강도'] > _T_거래강도)
                  & (df_1초.index > n_웜업) & (df_1초.index < self.n_장마감초)
                  & (df_1초['이격률'] >= _T_이격최소)).fillna(False).values
        ary_소멸 = (df_1초['순매수비율'] < 0).fillna(False).values
        ary_가격 = df_1초['price'].values
        ary_변동폭 = df_1초['변동폭300'].values

        # 거래 추출 (거래 단위 루프 - 내부는 numpy 벡터)
        li_dic거래 = list()
        n_길이 = len(ary_초)
        idx_진입후보 = np.where(ary_진입)[0]
        i = 0
        while len(li_dic거래) < _T_일최대거래:
            # 다음 진입 시점
            n_위치 = np.searchsorted(idx_진입후보, i)
            if n_위치 >= len(idx_진입후보):
                break
            i_진입 = int(idx_진입후보[n_위치])
            n_매수가 = ary_가격[i_진입]
            n_손절가 = n_매수가 * (1 - _T_손절 / 100)

            # 청산 시점 탐색 (벡터): 소멸(최소보유 이후) / 손절 / 장마감 중 최선
            i_시작 = i_진입 + 1
            ary_구간가격 = ary_가격[i_시작:]
            # 소멸: 최소보유 시간 이후부터만 유효
            ary_구간소멸 = ary_소멸[i_시작:].copy()
            ary_구간소멸[:_T_최소보유] = False
            i_소멸 = int(np.argmax(ary_구간소멸)) if ary_구간소멸.any() else n_길이
            i_손절 = int(np.argmax(ary_구간가격 <= n_손절가)) if (ary_구간가격 <= n_손절가).any() else n_길이
            i_마감 = int(np.searchsorted(ary_초[i_시작:], self.n_장마감초))
            i_마감 = i_마감 if i_마감 < len(ary_구간가격) else n_길이
            i_청산상대 = min(i_소멸, i_손절, i_마감)
            if i_청산상대 >= n_길이 or i_시작 + i_청산상대 >= n_길이:
                i_청산 = n_길이 - 1
                s_사유 = '타임아웃'
            else:
                i_청산 = i_시작 + i_청산상대
                s_사유 = ('손절터치' if i_청산상대 == i_손절 else
                        '소멸청산' if i_청산상대 == i_소멸 else '타임아웃')
            n_매도가 = n_손절가 if s_사유 == '손절터치' else ary_가격[i_청산]

            # MFE/MAE (벡터 슬라이스)
            ary_보유 = ary_가격[i_진입:i_청산 + 1]
            n_매수atr = max(ary_변동폭[i_진입] if not np.isnan(ary_변동폭[i_진입]) else 0, n_매수가 * 0.001)
            n_mfe단가 = float(ary_보유.max() - n_매수가)
            n_mae단가 = float(ary_보유.min() - n_매수가)

            # 거래 기록 (기존 거래내역 포맷 호환)
            n_수익률 = (n_매도가 / n_매수가 - 1) * 100 - _T_비용
            li_dic거래.append(dict(
                일자=s_일자, 종목코드=s_종목코드, 종목명=s_종목명, 전일일봉고가=n_전일고가,
                손절기준가=n_손절가, 목표기준가=n_매수가 + n_매수atr, 트레일링기준가=np.nan,
                매수신호=True, 매도신호=True,
                손절터치=(s_사유 == '손절터치'), 소멸청산=(s_사유 == '소멸청산'), 타임아웃=(s_사유 == '타임아웃'),
                보유신호=True,
                매수시점=self._초2시간(ary_초[i_진입]), 매도시점=self._초2시간(ary_초[i_청산]),
                매수가=n_매수가, 매도가=n_매도가, 수익률=n_수익률,
                매수atr=n_매수atr,
                mfe_단가=n_mfe단가, mae_단가=n_mae단가,
                mfe_수익률=n_mfe단가 / n_매수가 * 100, mae_수익률=n_mae단가 / n_매수가 * 100,
                mfe_매수atr=n_mfe단가 / n_매수atr, mae_매수atr=n_mae단가 / n_매수atr))

            # 다음 탐색 시작 (쿨다운)
            i = i_청산 + _T_쿨다운

        return pd.DataFrame(li_dic거래)

    @staticmethod
    def _초2시간(n_초):
        return f'{int(n_초) // 3600:02d}:{int(n_초) % 3600 // 60:02d}:{int(n_초) % 60:02d}'

    # -----------------------------------------------------------------
    def make_매매일보(self, b_카톡=False):
        """ 검증 결과 매매일보 생성 (돌파매매와 동일 포맷, 3분봉은 자체 캐시 사용) """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '40_결과정리')
        file_소스 = f'df_결과정리'
        folder_타겟 = os.path.join(self.folder_백테스팅, '50_매매일보')
        file_타겟 = f'df_매매일보'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매매일보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            df_결과정리 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            if df_결과정리.empty:
                continue
            df_결과정리 = df_결과정리.set_index('일자', drop=False)
            li_정리일자 = df_결과정리.index.tolist()

            # 추가 데이터 불러오기 - 누적거래, 일봉(서버캐시), 3분봉(자체캐시)
            df_누적거래 = pd.read_pickle(os.path.join(f'{folder_소스}_누적거래', f'df_누적거래_{s_일자}.pkl'))
            dic_일봉 = self._load_일봉캐시(s_일자=s_일자)
            path_3분봉 = os.path.join(self.folder_백테스팅, '20_매매정보_3분봉', f'dic_차트캐시_3분봉_{s_일자}.pkl')
            dic_3분봉 = pd.read_pickle(path_3분봉) if os.path.exists(path_3분봉) else dict()
            df_누적거래['주차'] = pd.to_datetime(df_누적거래['일자']).dt.isocalendar().week

            # 데이터 생성 (돌파매매와 동일 로직)
            li_dic매매일보 = list()
            for s_정리일자 in li_정리일자:
                df_정리 = df_누적거래.loc[df_누적거래['일자'] <= s_정리일자]
                df_수익 = df_정리.loc[df_정리['수익률'] > 0]
                df_손실 = df_정리.loc[df_정리['수익률'] <= 0]
                n_누적매매 = len(df_정리)
                n_누적수익매매, n_누적손실매매 = len(df_수익), len(df_손실)
                n_누적승률 = n_누적수익매매 / n_누적매매 * 100 if n_누적매매 > 0 else 0
                n_누적총손익 = df_정리['수익률'].sum() if n_누적매매 > 0 else 0
                n_누적평균수익 = df_수익['수익률'].mean() if n_누적수익매매 > 0 else 0
                n_누적평균손실 = df_손실['수익률'].mean() if n_누적손실매매 > 0 else 0
                n_누적손익비 = n_누적평균수익 / abs(n_누적평균손실) if n_누적평균손실 != 0 else 0
                n_누적기대치 = (n_누적승률 / 100 * n_누적손익비) - (1 - n_누적승률 / 100) if n_누적매매 > 0 else 0

                n_정리주차 = pd.Timestamp(s_정리일자).week
                df_주차 = df_누적거래.loc[df_누적거래['주차'] == n_정리주차]
                df_주수익 = df_주차.loc[df_주차['수익률'] > 0]
                df_주손실 = df_주차.loc[df_주차['수익률'] <= 0]
                n_주간매매 = len(df_주차)
                n_주간수익매매, n_주간손실매매 = len(df_주수익), len(df_주손실)
                n_주간승률 = n_주간수익매매 / n_주간매매 * 100 if n_주간매매 > 0 else 0
                n_주간총손익 = df_주차['수익률'].sum() if n_주간매매 > 0 else 0
                n_주간평균수익 = df_주수익['수익률'].mean() if n_주간수익매매 > 0 else 0
                n_주간평균손실 = df_주손실['수익률'].mean() if n_주간손실매매 > 0 else 0
                n_주간손익비 = n_주간평균수익 / abs(n_주간평균손실) if n_주간평균손실 != 0 else 0
                n_주간기대치 = (n_주간승률 / 100 * n_주간손익비) - (1 - n_주간승률 / 100) if n_주간매매 > 0 else 0

                dic_매매일보 = df_결과정리.loc[s_정리일자].to_dict()
                dic_매매일보.update(누적매매=n_누적매매, 누적수익매매=n_누적수익매매, 누적손실매매=n_누적손실매매,
                                누적승률=n_누적승률, 누적총손익=n_누적총손익, 누적평균수익=n_누적평균수익,
                                누적평균손실=n_누적평균손실, 누적손익비=n_누적손익비, 누적기대치=n_누적기대치,
                                주차=n_정리주차,
                                주간매매=n_주간매매, 주간수익매매=n_주간수익매매, 주간손실매매=n_주간손실매매,
                                주간승률=n_주간승률, 주간총손익=n_주간총손익, 주간평균수익=n_주간평균수익,
                                주간평균손실=n_주간평균손실, 주간손익비=n_주간손익비, 주간기대치=n_주간기대치)
                li_dic매매일보.append(dic_매매일보)

            # 매매일보 df 생성
            df_매매일보 = (pd.DataFrame(li_dic매매일보).set_index('일자', drop=False).sort_index()
                       if len(li_dic매매일보) > 0 else pd.DataFrame())
            df_당일거래 = df_누적거래.loc[df_누적거래['일자'] == s_일자].copy().sort_values(['종목코드', '매수시점']).reset_index(drop=True)
            df_당일거래['매도사유'] = df_당일거래[['손절터치', '소멸청산', '타임아웃']].idxmax(axis=1).where(
                                    df_당일거래[['손절터치', '소멸청산', '타임아웃']].any(axis=1))

            # 개별 차트 대상 제한 - 거래 과다 시 |수익률| 상위만 (파일 과대 방지)
            if len(df_당일거래) > _T_차트최대:
                idx_차트 = df_당일거래['수익률'].abs().sort_values(ascending=False).index[:_T_차트최대]
                df_차트거래 = (df_당일거래.loc[idx_차트].sort_values(['종목코드', '매수시점']).reset_index(drop=True))
            else:
                df_차트거래 = df_당일거래

            # 그래프 생성 (돌파매매와 동일 구성)
            n_차트_세로 = 1 + len(df_차트거래)
            fig = plt.figure(figsize=(16, n_차트_세로 * 3), tight_layout=True)
            gs = GridSpec(nrows=n_차트_세로, ncols=3, figure=fig)

            ax_누적기대치 = fig.add_subplot(gs[0, 0])
            ax_mfe산점도 = fig.add_subplot(gs[0, 1])
            ax_거래별mfe = fig.add_subplot(gs[0, 2])
            self.chart.ax_누적기대치(ax=ax_누적기대치, df_매매일보=df_매매일보)
            self.chart.ax_mfe산점도(ax=ax_mfe산점도, df_누적거래=df_누적거래)
            self.chart.ax_거래별mfe(ax=ax_거래별mfe, df_누적거래=df_누적거래)

            for idx in df_차트거래.index:
                dic_거래정보 = df_차트거래.loc[idx].to_dict()
                s_종목코드 = dic_거래정보.get('종목코드', None)
                dic_거래정보.update(df_일봉=dic_일봉.get(s_종목코드, pd.DataFrame()),
                                df_3분봉=dic_3분봉.get(s_종목코드, pd.DataFrame()))
                ax_일봉거래 = fig.add_subplot(gs[1 + idx, 0])
                ax_3분봉거래 = fig.add_subplot(gs[1 + idx, 1:])
                self.chart.ax_일봉거래(ax=ax_일봉거래, dic_거래정보=dic_거래정보)
                self.chart.ax_3분봉거래(ax=ax_3분봉거래, dic_거래정보=dic_거래정보)

            # 그래프 저장
            file_그래프 = f'{file_타겟}_{s_일자}.svg'
            os.makedirs(folder_그래프 := f'{folder_타겟}_그래프', exist_ok=True)
            fig.savefig(os.path.join(folder_그래프, file_그래프))
            if sys.platform == 'darwin':
                os.system(f'xattr -d com.apple.quarantine {os.path.join(folder_그래프, file_그래프)} 2>/dev/null')
            plt.close(fig)

            # 매매일보 저장
            self.tool.df저장(df=df_매매일보, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 그래프 웹서버 복사
            s_전략명 = '틱기반매수세'
            li_파일일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_그래프) if '.svg' in 파일]
            n_파일보관일수 = (pd.Timestamp(s_일자) - pd.Timestamp(min(li_파일일자))).days if len(li_파일일자) > 0 else self.n_검증일수
            li_복사한파일명, li_삭제한파일명, dic_서버정보 = self.tool.sftp파일업로드(
                folder_로컬=folder_그래프, s_서버폴더=s_전략명, s_파일명=file_그래프, n_파일보관일수=n_파일보관일수)

            # 메세지 송부
            if b_카톡 and s_일자 == li_대상일자[-1]:
                s_url주소 = f'http://{dic_서버정보['sftp']['hostname']}/kakao/{s_전략명}'
                self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=f'[{s_일자}] 백테스팅 완료',
                                    s_버튼이름=f'[{s_전략명}] {file_그래프}', s_연결url=f'{s_url주소}/{file_그래프}')

            # 로그 기록
            self.make_로그(f'{s_일자}')


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def run():
    """ 실행 함수 """
    a = AnalyzerBot(n_검증일수=60, b_디버그모드=False)
    a.pick_종목선정()
    a.make_매매정보()
    a.make_거래내역()
    a.make_결과정리()
    a.make_매매일보(b_카톡=True)


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
