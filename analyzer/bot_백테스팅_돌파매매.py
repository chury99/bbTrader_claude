import os
import sys
import json
import time
import re

import pandas as pd
import dataframe_image as dfi
from tqdm import tqdm
import multiprocessing as mp
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

import analyzer, ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker
class AnalyzerBot:
    # noinspection PyUnresolvedReferences
    def __init__(self, n_검증일수, b_디버그모드):
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
        # self.folder_대상종목 = dic_폴더정보['데이터|대상종목']
        # self.folder_조회순위 = dic_폴더정보['데이터|조회순위']
        # self.folder_차트정보 = dic_폴더정보['데이터|차트정보']
        # self.folder_분석 = dic_폴더정보['분석']
        self.folder_백테스팅 = os.path.join(dic_폴더정보['분석|백테스팅'], '돌파매매')
        os.makedirs(self.folder_백테스팅, exist_ok=True)

        # 추가 폴더 정의
        self.folder_spv2 = ('/Users/ProjectWork/spTraderV2' if sys.platform == 'darwin' else
                            'E:/ProjectWork/spTraderV2' if sys.platform == 'win32' else '')
        self.folder_서버 = ('/Volumes/extSSD4tb/80_Backup/10_python_backup/ProjectWork/spTraderV2'
                          if sys.platform == 'darwin' else '')

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.n_검증일수 = n_검증일수
        self.b_디버그모드 = b_디버그모드
        self.n_멀티코어수 = mp.cpu_count() - 3

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()
        # self.logic = analyzer.logic_백테스팅
        self.chart = ut.차트maker.ChartMaker()

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def pick_종목선정(self):
        """ 조회순위 데이터 기준으로 전일일봉 확인하여 대상종목 선정 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_서버, '데이터', '차트캐시', '일봉1')
        file_소스 = f'dic_차트캐시_1일봉'
        folder_타겟 = os.path.join(self.folder_백테스팅, '10_종목선정')
        file_타겟 = f'df_종목선정'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_전체일자 = li_전체일자[-self.n_검증일수:]
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 대상종목 선정
        for s_일자 in li_대상일자:
            # 소스 데이터 읽어오기
            path_일봉 = os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl')
            dic_일봉 = pd.read_pickle(path_일봉) if os.path.exists(path_일봉) else None
            if dic_일봉 is None: continue

            # 추가 데이터 불러오기 - 전일 데이터 기준으로 당일 후보종목 생성
            li_일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스) if '.pkl' in 파일]
            s_전일 = max(일자 for 일자 in li_일자 if 일자 < s_일자)
            path_거래대상 = os.path.join(self.folder_서버, '데이터', '대상종목', f'df_대상종목_{s_전일}.pkl')
            path_조회순위 = os.path.join(self.folder_서버, '데이터', '조회순위_tr', f'df_조회순위_{s_전일}.csv')
            df_거래대상 = pd.read_pickle(path_거래대상) if os.path.exists(path_거래대상) else None
            df_조회순위 = (pd.read_csv(path_조회순위, encoding='cp949', dtype=str, on_bad_lines='skip')
                       if os.path.exists(path_조회순위) else None)
            if (df_거래대상 is None) or (df_조회순위 is None): continue

            # 대상종목 선정
            li_거래대상 = [종목 for 종목 in dic_일봉.keys() if 종목 in df_거래대상['종목코드'].values]
            li_대상종목 = [종목 for 종목 in li_거래대상 if 종목 in df_조회순위['종목코드'].values]

            # 종목별 데이터 생성
            li_dic종목선정 = list()
            for s_종목코드 in li_대상종목:
                # 기준정보 정의
                df_일봉 = dic_일봉.get(s_종목코드, None)
                if (df_일봉 is None) or (len(df_일봉) < 2): continue
                # s_등장시간 = df_조회순위.loc[s_종목코드, '시간']

                # 데이터 생성
                dt_당일 = df_일봉.index[-1]
                dt_전일 = df_일봉.index[-2]
                df_일봉['고가20'] = df_일봉['고가'].shift(1).rolling(20).max()
                n_전일시가 = df_일봉.loc[dt_전일, '시가']
                n_전일고가 = df_일봉.loc[dt_전일, '고가']
                n_전일저가 = df_일봉.loc[dt_전일, '저가']
                n_전일종가 = df_일봉.loc[dt_전일, '종가']
                n_전일고가20 = df_일봉.loc[dt_전일, '고가20']
                n_전일상승률 = df_일봉.loc[dt_전일, '전일대비(%)']
                n_전일ma5 = df_일봉.loc[dt_전일, '종가ma5']
                n_전일ma20 = df_일봉.loc[dt_전일, '종가ma20']
                n_전일ma120 = df_일봉.loc[dt_전일, '종가ma120']
                n_전일거래량 = df_일봉.loc[dt_전일, '거래량']
                n_전일거래량ma20 = df_일봉.loc[dt_전일, '거래량ma20']
                n_전일변동성 = (n_전일고가 - n_전일저가) / n_전일종가 * 100
                n_거래량비율 = n_전일거래량 / n_전일거래량ma20
                n_종가위치 = (n_전일종가 - n_전일저가) / (n_전일고가 - n_전일저가) if (n_전일고가 - n_전일저가) > 0 else 0

                # 종목 선정
                b_전일돌파 = (n_전일종가 > n_전일고가20) and (n_전일상승률 < 29)
                b_거래량비율 = n_거래량비율 > 2
                b_상승률 = 8 < n_전일상승률 < 29
                b_종가위치 =  n_종가위치 > 0.7
                b_종목선정 = b_전일돌파 and b_상승률 and b_종가위치

                b_전일정배열 = n_전일ma5 > n_전일ma20 > n_전일ma120
                b_전일양봉마감 = n_전일종가 > n_전일시가
                b_전일거래증가 = n_전일거래량 > 2 * n_전일거래량ma20
                b_전일고가접근 = n_전일종가 / n_전일고가 > 0.95
                b_전일변동제한 = n_전일변동성 < 10
                # b_종목선정 = b_전일돌파 and b_전일정배열
                # b_종목선정 = b_전일정배열 and b_전일양봉마감 and b_전일거래증가 and b_전일고가접근 and b_전일변동제한

                # 전달용 데이터 생성
                n_전일일봉고가 = max(n_전일고가, n_전일고가20)
                n_전일일봉고가율 = (n_전일일봉고가 - n_전일종가) / n_전일종가 * 100

                # 결과 검증용 데이터 생성
                n_당일고가 = df_일봉.loc[dt_당일, '고가']
                n_당일고가상승률 = (n_당일고가 - n_전일종가) / n_전일종가 * 100
                b_당일수익 = ((n_당일고가상승률 - n_전일일봉고가율) > 5) and b_종목선정

                # 결과 생성
                dic_종목선정 = df_일봉.iloc[-1].to_dict()
                dic_종목선정.update(전일시가=n_전일시가, 전일고가=n_전일고가, 전일저가=n_전일저가, 전일종가=n_전일종가,
                                전일고가20=n_전일고가20, 전일상승률=n_전일상승률,
                                전일ma5=n_전일ma5, 전일ma20=n_전일ma20, 전일ma120=n_전일ma120,
                                전일거래량=n_전일거래량, 전일거래량ma20=n_전일거래량ma20,
                                전일변동성=n_전일변동성,
                                전일돌파=b_전일돌파, 전일정배열=b_전일정배열, 전일양봉마감=b_전일양봉마감, 전일거래증가=b_전일거래증가,
                                전일고가접근=b_전일고가접근, 전일변동제한=b_전일변동제한,
                                종목선정=b_종목선정,
                                전일일봉고가=n_전일일봉고가, 전일일봉고가율=n_전일일봉고가율,당일고가상승률=n_당일고가상승률,
                                당일수익=b_당일수익)
                li_dic종목선정.append(dic_종목선정)

            # 데이터 정리
            df_종목선정 = pd.DataFrame(li_dic종목선정) if len(li_dic종목선정) > 0 else pd.DataFrame()

            # 결과 저장
            self.tool.df저장(df=df_종목선정, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 일봉 저장
            os.makedirs(folder_일봉 := f'{folder_타겟}_일봉', exist_ok=True)
            pd.to_pickle(dic_일봉, os.path.join(folder_일봉, f'dic_차트캐시_1일봉_{s_일자}.pkl'))

            # 로그 기록
            n_전체종목수 = len(df_종목선정)
            n_선정종목수 = len(df_종목선정[df_종목선정['종목선정']])
            n_수익종목수 = len(df_종목선정[df_종목선정['당일수익']])
            n_성공률 = n_수익종목수 / n_선정종목수 * 100 if n_선정종목수 != 0 else 0
            self.make_로그(f'{s_일자} - {n_수익종목수:,.0f} / {n_선정종목수:,.0f} / {n_전체종목수:,.0f}종목 - {n_성공률:,.0f}%')

    def make_매매정보(self):
        """ 선정된 종목에 대해 매수매도 정보 생성 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '10_종목선정')
        file_소스 = f'df_종목선정'
        folder_타겟 = os.path.join(self.folder_백테스팅, '20_매매정보')
        file_타겟 = f'dic_매매정보'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            df_종목선정 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            df_종목선정 = df_종목선정.set_index('종목코드', drop=False)
            li_대상종목 = df_종목선정.loc[df_종목선정['종목선정']]['종목코드'].tolist()

            # 추가정보 불러오기 - 3분봉
            folder_3분봉 = os.path.join(self.folder_서버, '데이터', '차트캐시', '분봉3')
            li_파일 = sorted(파일 for 파일 in sorted(os.listdir(folder_3분봉))
                           if re.findall(r'\d{8}', 파일)[0] <= s_일자 and '.pkl' in 파일)
            dic_3분봉_전일 = pd.read_pickle(os.path.join(folder_3분봉, li_파일[-2])) if len(li_파일) >= 2 else dict()
            dic_3분봉_당일 = pd.read_pickle(os.path.join(folder_3분봉, li_파일[-1])) if len(li_파일) >= 1 else dict()
            dic_3분봉 = {종목코드: pd.concat([dic_3분봉_전일.get(종목코드, pd.DataFrame()), dic_3분봉_당일.get(종목코드, pd.DataFrame())])
                       for 종목코드 in dic_3분봉_당일.keys()}

            # 추가정보 불러오기 - 1분봉 - 체결가 확인용
            path_1분봉 = os.path.join(self.folder_서버, '데이터', '차트캐시', '분봉1', f'dic_차트캐시_1분봉_{s_일자}.pkl')
            dic_1분봉 = pd.read_pickle(path_1분봉) if os.path.exists(path_1분봉) else None
            if dic_1분봉 is None: continue

            # # 추가정보 불러오기 - 체결정보
            # path_체결 = os.path.join(self.folder_서버, '데이터', '주식체결_ws', f'주식체결_{s_일자}.csv')
            # df_체결 = (pd.read_csv(path_체결, encoding='cp949', dtype=str, on_bad_lines='skip')
            #            if os.path.exists(path_체결) else None)
            # if df_체결 is None: continue
            # df_체결['체결시간'] = df_체결['체결시간'].str[:2] + ':' + df_체결['체결시간'].str[2:4] + ':' + df_체결['체결시간'].str[4:]
            # gr_체결 = df_체결.groupby('종목코드')
            # dic_체결 = {종목코드: gr_체결.get_group(종목코드) for 종목코드 in gr_체결.groups.keys()}

            # 매개변수 정의 - 함수 전달용
            li_매개변수 = [dict(s_종목코드=s_종목코드, s_일자=s_일자,
                            folder_타겟=folder_타겟, file_타겟=file_타겟,
                            df_종목선정=df_종목선정,
                            df_3분봉=dic_3분봉.get(s_종목코드, pd.DataFrame()),
                            df_1분봉=dic_1분봉.get(s_종목코드, pd.DataFrame()))
                       for s_종목코드 in li_대상종목]

            # 종목별 매수매도 정보 생성
            li_df매매정보 = list()
            if self.b_디버그모드:
                for dic_매개변수 in tqdm(li_매개변수, desc=f'매매정보-{s_일자}', file=sys.stdout):
                    li_df매매정보.append(self._make_매매정보_종목(dic_매개변수=dic_매개변수))
            else:
                with mp.Pool(processes=self.n_멀티코어수) as pool:
                    li_df매매정보 = list(tqdm(pool.imap_unordered(self._make_매매정보_종목, li_매개변수),
                                          total=len(li_매개변수), desc=f'매매정보-{s_일자}', file=sys.stdout))
            dic_매매정보 = dict(li_df매매정보)

            # 데이터 저장
            pd.to_pickle(dic_매매정보, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 분봉 저장
            os.makedirs(folder := f'{folder_타겟}_3분봉', exist_ok=True)
            pd.to_pickle(dic_3분봉[dic_3분봉['일자'] == s_일자], os.path.join(folder, f'dic_차트캐시_3분봉_{s_일자}.pkl'))
            os.makedirs(folder := f'{folder_타겟}_1분봉', exist_ok=True)
            pd.to_pickle(dic_1분봉, os.path.join(folder, f'dic_차트캐시_1분봉_{s_일자}.pkl'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(dic_매매정보)}종목')

        # 전체일자 파일 생성 - 클로드 입력용
        li_일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟) if '.pkl' in 파일)
        dic_전체일자 = {일자: pd.read_pickle(os.path.join(folder_타겟, f'{file_타겟}_{일자}.pkl')) for 일자 in li_일자}
        os.makedirs(folder := f'{folder_타겟}_전체일자', exist_ok=True)
        pd.to_pickle(dic_전체일자, os.path.join(folder, f'{file_타겟}_전체일자_{max(li_일자)}.pkl'))

    def make_거래내역(self):
        """ 매수매도 결과를 바탕으로 거래내역 정리 """
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

        # 일자별 거래내역 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            dic_매매정보 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            li_대상종목 = list(dic_매매정보.keys())

            # 거래내역 정리
            li_df거래내역 = list()
            for s_종목코드 in li_대상종목:
                # 기준정보 설정
                df_매매정보 = dic_매매정보.get(s_종목코드, None)
                if (df_매매정보.empty) or (df_매매정보 is None): continue
                s_종목명 = df_매매정보['종목명'].values[0]

                # MAE / MFE 생성
                df_매매정보['보유그룹'] = (df_매매정보['보유신호'] != df_매매정보['보유신호'].shift(1)).cumsum()
                df_매매정보['mfe_단가'] = df_매매정보.groupby('보유그룹')['고가'].transform('max') - df_매매정보['매수가']
                df_매매정보['mae_단가'] = df_매매정보.groupby('보유그룹')['저가'].transform('min') - df_매매정보['매수가']
                df_매매정보.loc[~df_매매정보['보유신호'], ['mfe_단가', 'mae_단가']] = None
                df_매매정보['mfe_수익률'] = df_매매정보['mfe_단가'] / df_매매정보['매수가'] * 100
                df_매매정보['mae_수익률'] = df_매매정보['mae_단가'] / df_매매정보['매수가'] * 100
                df_매매정보['mfe_매수atr'] = df_매매정보['mfe_단가'] / df_매매정보['매수atr']
                df_매매정보['mae_매수atr'] = df_매매정보['mae_단가'] / df_매매정보['매수atr']

                # 매매결과 생성
                li_컬럼 = ['일자', '종목코드', '종목명', '전일일봉고가',
                         '손절기준가', '목표기준가', '트레일링기준가',
                         '매수신호', '매도신호', '손절터치', '목표터치', '트레일링', '타임아웃', '보유신호',
                         '매수시점', '매도시점', '매수가', '매도가', '수익률',
                         '매수atr', 'mfe_단가', 'mae_단가', 'mfe_수익률', 'mae_수익률', 'mfe_매수atr', 'mae_매수atr']
                df_매매결과 = df_매매정보.loc[df_매매정보['매도시점'].notnull(), li_컬럼]
                li_df거래내역.append(df_매매결과)

            # df 생성
            df_거래내역 = pd.concat(li_df거래내역) if len(li_df거래내역) > 0 else pd.DataFrame()
            df_거래내역 = df_거래내역.sort_values('매수시점') if not df_거래내역.empty else df_거래내역

            # 데이터 저장
            self.tool.df저장(df=df_거래내역, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 지표 정의
            df_거래내역_수익 = df_거래내역.loc[df_거래내역['수익률'] > 0] if not df_거래내역.empty else pd.DataFrame()
            df_거래내역_손실 = df_거래내역.loc[df_거래내역['수익률'] <= 0] if not df_거래내역.empty else pd.DataFrame()
            n_총매매 = len(df_거래내역)
            n_수익매매 = len(df_거래내역_수익)
            n_손실매매 = len(df_거래내역_손실)
            n_승률 = n_수익매매 / n_총매매 * 100 if n_총매매 > 0 else 0
            n_총손익률 = df_거래내역['수익률'].sum() if n_총매매 > 0 else 0
            n_평균수익률 = df_거래내역_수익['수익률'].mean() if n_수익매매 > 0 else 0
            n_평균손실률 = df_거래내역_손실['수익률'].mean() if n_손실매매 > 0 else 0
            n_손익비 = n_평균수익률 / abs(n_평균손실률) if n_평균손실률 != 0 else 0
            n_기대치 = (n_승률 / 100 * n_손익비) - (1 - n_승률 / 100)

            # 로그 기록
            self.make_로그(f'{s_일자}\n'
                         f' - 기대치 {n_기대치:,.2f}, 총수익 {n_총손익률:,.0f}%\n'
                         f' - 승률 {n_승률:,.0f}% (총 {n_총매매}, 승 {n_수익매매}, 패 {n_손실매매})\n'
                         f' - 손익비 {n_손익비:,.1f} (평균수익 {n_평균수익률:,.0f}%, 평균손실 {n_평균손실률:,.0f}%)')

    def make_결과정리(self):
        """ 검증기간 동안의 전체 결과 정리 """
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

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            li_파일일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스) if '.pkl' in 파일]
            li_파일일자 = [일자 for 일자 in li_파일일자 if 일자 <= s_일자]

            # 결과정리
            li_dic결과정리 = list()
            li_df누적거래 = list()
            for s_파일일자 in li_파일일자:
                # 기준정보 정의
                df_거래내역 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_파일일자}.pkl'))
                if df_거래내역.empty: continue

                # 지표 생성
                df_손익정리_수익 = df_거래내역.loc[df_거래내역['수익률'] > 0]
                df_손익정리_손실 = df_거래내역.loc[df_거래내역['수익률'] <= 0]
                n_일간매매 = len(df_거래내역)
                n_일간수익매매 = len(df_손익정리_수익)
                n_일간손실매매 = len(df_손익정리_손실)
                n_일간승률 = n_일간수익매매 / n_일간매매 * 100 if n_일간매매 > 0 else 0
                n_일간총손익 = df_거래내역['수익률'].sum() if n_일간매매 > 0 else 0
                n_일간평균수익 = df_손익정리_수익['수익률'].mean() if n_일간수익매매 > 0 else 0
                n_일간평균손실 = df_손익정리_손실['수익률'].mean() if n_일간손실매매 > 0 else 0
                n_일간손익비 = n_일간평균수익 / abs(n_일간평균손실) if n_일간평균손실 != 0 else 0
                n_일간기대치 = (n_일간승률 / 100 * n_일간손익비) - (1 - n_일간승률 / 100)

                # 결과 생성
                dic_결과정리 = dict(일자=s_파일일자,
                                일간매매=n_일간매매, 일간수익매매=n_일간수익매매, 일간손실매매=n_일간손실매매, 일간승률=n_일간승률,
                                일간총손익=n_일간총손익, 일간평균수익=n_일간평균수익, 일간평균손실=n_일간평균손실, 일간손익비=n_일간손익비,
                                일간기대치=n_일간기대치)
                li_dic결과정리.append(dic_결과정리)
                li_df누적거래.append(df_거래내역)

            # df 생성
            df_결과정리 = pd.DataFrame(li_dic결과정리).sort_values('일자') if len(li_dic결과정리) > 0 else pd.DataFrame()
            df_누적거래 = pd.concat(li_df누적거래).sort_values(['일자', '매수시점']) if len(li_df누적거래) > 0 else pd.DataFrame()

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
            n_누적기대치 = (n_누적승률 / 100 * n_누적손익비) - (1 - n_누적승률 / 100)

            # 로그 기록
            n_누적일수 = len(df_결과정리)
            self.make_로그(f'{s_일자}({n_누적일수}일)\n'
                         f' - 누적기대치 {n_누적기대치:,.2f}, 누적수익 {n_누적총손익:,.0f}%\n'
                         f' - 누적승률 {n_누적승률:,.0f}% (총 {n_누적매매}, 승 {n_누적수익매매}, 패 {n_누적손실매매})\n'
                         f' - 누적손익비 {n_누적손익비:,.1f} (평균수익 {n_누적평균수익:,.0f}%, 평균손실 {n_누적평균손실:,.0f}%)')

    def make_매매일보(self, b_카톡=False):
        """ 검증 결과에 대해 그래프 기반의 보고서 생성 """
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

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            df_결과정리 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            df_결과정리 = df_결과정리.set_index('일자', drop=False)
            li_정리일자 = df_결과정리.index.tolist()

            # 추가 데이터 불러오기
            # df_거래내역 = pd.read_pickle(os.path.join(self.folder_백테스팅, '30_거래내역', f'df_거래내역_{s_일자}.pkl'))
            df_누적거래 = pd.read_pickle(os.path.join(self.folder_백테스팅, f'{folder_소스}_누적거래', f'df_누적거래_{s_일자}.pkl'))
            dic_일봉 = pd.read_pickle(os.path.join(self.folder_서버, '데이터', '차트캐시', '일봉1', f'dic_차트캐시_1일봉_{s_일자}.pkl'))
            dic_3분봉 = pd.read_pickle(os.path.join(self.folder_서버, '데이터', '차트캐시', '분봉3', f'dic_차트캐시_3분봉_{s_일자}.pkl'))

            # 데이터 생성
            li_dic매매일보 = list()
            for s_정리일자 in li_정리일자:
                # 데이터 정의 - 누적
                df_누적거래_정리일자 = df_누적거래.loc[df_누적거래['일자'] <= s_정리일자]
                df_누적거래_정리일자_수익 = df_누적거래_정리일자.loc[df_누적거래_정리일자['수익률'] > 0]
                df_누적거래_정리일자_손실 = df_누적거래_정리일자.loc[df_누적거래_정리일자['수익률'] <= 0]
                n_누적매매 = len(df_누적거래_정리일자)
                n_누적수익매매 = len(df_누적거래_정리일자_수익)
                n_누적손실매매 = len(df_누적거래_정리일자_손실)
                n_누적승률 = n_누적수익매매 / n_누적매매 * 100 if n_누적매매 > 0 else 0
                n_누적총손익 = df_누적거래_정리일자['수익률'].sum() if n_누적매매 > 0 else 0
                n_누적평균수익 = df_누적거래_정리일자_수익['수익률'].mean() if n_누적수익매매 > 0 else 0
                n_누적평균손실 = df_누적거래_정리일자_손실['수익률'].mean() if n_누적손실매매 > 0 else 0
                n_누적손익비 = n_누적평균수익 / abs(n_누적평균손실) if n_누적평균손실 != 0 else 0
                n_누적기대치 = (n_누적승률 / 100 * n_누적손익비) - (1 - n_누적승률 / 100)

                # 매매일보 생성
                dic_매매일보 = df_결과정리.loc[s_정리일자].to_dict()
                dic_매매일보.update(누적매매=n_누적매매, 누적수익매매=n_누적수익매매, 누적손실매매=n_누적손실매매, 누적승률=n_누적승률,
                                누적총손익=n_누적총손익, 누적평균수익=n_누적평균수익, 누적평균손실=n_누적평균손실, 누적손익비=n_누적손익비,
                                누적기대치=n_누적기대치)
                li_dic매매일보.append(dic_매매일보)

            # 매매일보 생성
            df_매매일보 = (pd.DataFrame(li_dic매매일보).set_index('일자', drop=False).sort_index()
                       if len(li_dic매매일보) > 0 else pd.DataFrame())
            df_당일거래 = df_누적거래.loc[df_누적거래['일자'] == s_일자].copy().sort_values(['종목코드', '매수시점']).reset_index(drop=True)
            df_당일거래['매도사유'] = df_당일거래[['손절터치', '트레일링', '타임아웃']].idxmax(axis=1).where(
                                    df_당일거래[['손절터치', '트레일링', '타임아웃']].any(axis=1))

            # 그래프 생성
            n_차트_가로 = 3
            n_차트_세로 = 1 + len(df_당일거래)
            # fig, axes = plt.subplots(nrows=n_차트_세로, ncols=n_차트_가로, figsize=(16, n_차트_세로 * 3), tight_layout=True)
            fig = plt.figure(figsize=(16, n_차트_세로 * 3), tight_layout=True)
            gs = GridSpec(nrows=n_차트_세로, ncols=n_차트_가로, figure=fig)

            # 기본요약 구성
            ax_누적기대치 = fig.add_subplot(gs[0, 0])
            ax_mfe산점도 = fig.add_subplot(gs[0, 1])
            ax_거래별mfe = fig.add_subplot(gs[0, 2])
            ax_누적기대치 = self.chart.ax_누적기대치(ax=ax_누적기대치, df_매매일보=df_매매일보)
            ax_mfe산점도 = self.chart.ax_mfe산점도(ax=ax_mfe산점도, df_누적거래=df_누적거래)
            ax_거래별mfe = self.chart.ax_거래별mfe(ax=ax_거래별mfe, df_누적거래=df_누적거래)

            # 당일 거래차트 구성
            for idx in df_당일거래.index:
                # 기준정보 정의
                dic_거래정보 = df_당일거래.loc[idx].to_dict()
                s_종목코드 = dic_거래정보.get('종목코드', None)
                dic_거래정보.update(df_일봉=dic_일봉.get(s_종목코드, pd.DataFrame()),
                                df_3분봉=dic_3분봉.get(s_종목코드, pd.DataFrame()))
                ax_일봉거래 = fig.add_subplot(gs[1 + idx, 0])
                ax_3분봉거래 = fig.add_subplot(gs[1 + idx, 1:])

                # 차트 구성
                ax_일봉거래 = self.chart.ax_일봉거래(ax=ax_일봉거래, dic_거래정보=dic_거래정보)
                ax_3분봉거래 = self.chart.ax_3분봉거래(ax=ax_3분봉거래, dic_거래정보=dic_거래정보)

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
            s_전략명 = '돌파매매'
            li_복사한파일명, li_삭제한파일명, dic_서버정보 = self.tool.sftp파일업로드(folder_로컬=folder_그래프,
                                                         s_서버폴더=s_전략명, s_파일명=file_그래프, n_파일보관일수=self.n_검증일수)

            # 메세지 송부
            if b_카톡 and s_일자 == li_대상일자[-1]:
                # 기준정보 정의
                s_url주소 = f'http://{dic_서버정보['sftp']['hostname']}/kakao/{s_전략명}'

                # 일보 송부
                self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=f'[{s_일자}] 백테스팅 완료',
                                    s_버튼이름=f'[{s_전략명}] {file_그래프}', s_연결url=f'{s_url주소}/{file_그래프}')

                # 폴더 송부
                # self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=f'[{s_일자}] 백테스팅 완료',
                #                     s_버튼이름=f'[{s_전략명}] 매매일보 폴더', s_연결url=f'{s_url주소}/')

            # 로그 기록 - 나중에 익절 / 손절 기준가 표기 (R로 표기)
            self.make_로그(f'{s_일자}')

    def _make_매매정보_종목(self, dic_매개변수):
        """ 종목별 매수매도 정보 생성 후 리턴 """
        # 기준정보 정의
        s_종목코드 = dic_매개변수.get('s_종목코드', None)
        s_일자 = dic_매개변수.get('s_일자', None)
        folder_타겟 = dic_매개변수.get('folder_타겟', None)
        file_타겟 = dic_매개변수.get('file_타겟', None)
        df_종목선정 = dic_매개변수.get('df_종목선정', pd.DataFrame())
        df_3분봉 = dic_매개변수.get('df_3분봉', pd.DataFrame())
        df_1분봉 = dic_매개변수.get('df_1분봉', pd.DataFrame())
        if (len(df_종목선정) == 0) or (len(df_3분봉) == 0) or (len(df_1분봉) == 0):
            return s_종목코드, pd.DataFrame()

        # 추가정보 생성
        s_종목명 = df_종목선정.loc[s_종목코드, '종목명']
        n_전일일봉고가 = df_종목선정.loc[s_종목코드, '전일일봉고가']

        # 지표 생성
        df_3분봉['직전ma5'] = df_3분봉['종가ma5'].shift(1)
        df_3분봉['직전ma20'] = df_3분봉['종가ma20'].shift(1)
        df_3분봉['직전ma120'] = df_3분봉['종가ma120'].shift(1)
        df_3분봉['고가20'] = df_3분봉['고가'].shift(1).rolling(20).max()
        df_3분봉['tr'] = pd.concat([df_3분봉['고가'] - df_3분봉['저가'],
                                   (df_3분봉['고가'] - df_3분봉['종가'].shift(1)).abs(),
                                   (df_3분봉['저가'] - df_3분봉['종가'].shift(1)).abs()], axis=1).max(axis=1)
        df_3분봉['직전atr'] = df_3분봉['tr'].ewm(span=14, adjust=False).mean().shift(1)
        df_3분봉['직전고가'] = df_3분봉['고가'].shift(1)
        df_3분봉['직전종가'] = df_3분봉['종가'].shift(1)
        df_3분봉_당일 = df_3분봉.loc[df_3분봉['일자'] == s_일자]
        df_3분봉['당일고가'] = [None] * (len(df_3분봉) - len(df_3분봉_당일)) + df_3분봉_당일['고가'].cummax().shift(1).tolist()
        df_3분봉['전일일봉고가'] = n_전일일봉고가

        # 당일 데이터만 사용
        df_3분봉 = df_3분봉[df_3분봉['일자'] == s_일자]

        # # 체결정보 숫자로 변환
        # df_체결['현재가'] = df_체결['현재가'].astype(int).abs()

        # 등장시간 반영
        # df_3분봉 = df_3분봉.loc[df_3분봉.index >= dt_등장시간]
        # df_3분봉['등장시간'] = s_등장시간

        # 매매정보 생성
        li_dic매매정보 = list()
        n_매수후고가 = None
        b_매수신호, b_매도신호, b_보유신호 = False, False, False
        for idx in df_3분봉.index:
            # 기준정보 설정
            dic_3분봉_시점 = df_3분봉.loc[idx].to_dict()
            s_분봉시간 = dic_3분봉_시점.get('시간')
            n_시가 = dic_3분봉_시점.get('시가')
            n_고가 = dic_3분봉_시점.get('고가')
            n_저가 = dic_3분봉_시점.get('저가')
            n_종가 = dic_3분봉_시점.get('종가')
            n_직전고가 = dic_3분봉_시점.get('직전고가')
            n_직전종가 = dic_3분봉_시점.get('직전종가')
            n_고가20 = dic_3분봉_시점.get('고가20')
            n_직전atr = dic_3분봉_시점.get('직전atr')
            n_직전ma5 = dic_3분봉_시점.get('직전ma5')
            n_직전ma20 = dic_3분봉_시점.get('직전ma20')
            n_직전ma120 = dic_3분봉_시점.get('직전ma120')
            n_당일고가 = dic_3분봉_시점.get('당일고가') if pd.notna(dic_3분봉_시점.get('당일고가')) else 0

            # 매수신호 확인
            b_돌파여부, b_배열필터, b_시간필터 = False, False, False
            # n_매수기준가 = max(n_전일일봉고가, n_당일고가)
            n_매수기준가 = max(n_전일일봉고가, n_고가20)
            if not b_보유신호:
                # 3분봉 확인
                b_돌파여부 = n_고가 > n_매수기준가
                # b_배열필터 = n_직전ma5 > n_직전ma20
                # b_배열필터 = n_직전종가 > n_직전ma120
                b_배열필터 = n_직전ma5 > n_직전ma120
                b_시간필터 = s_분봉시간 < '13:00:00'
                # b_매수정보탐색 = b_돌파여부 and b_배열필터 and b_시간필터

                # 매수정보 확인 - 1분봉 확인
                if b_돌파여부 and b_배열필터 and b_시간필터:
                    # 1분봉 정보 필터링 - 3분봉 1개 봉
                    s_다음분봉시간 = min(시간 for 시간 in df_3분봉['시간'].values if 시간 > s_분봉시간)
                    df_1분봉_대상 = df_1분봉[(df_1분봉['시간'] >= s_분봉시간) & (df_1분봉['시간'] < s_다음분봉시간)]

                    # 1분봉 정보 확인
                    for idx_1분봉 in df_1분봉_대상.index:
                        # 매수신호 확인
                        n_고가_1분봉 = df_1분봉_대상.loc[idx_1분봉, '고가']
                        b_돌파여부 = n_고가_1분봉 > n_매수기준가
                        b_매수신호 = b_돌파여부 and b_배열필터 and b_시간필터

                        # 매수정보 생성
                        if b_매수신호:
                            n_시가_1분봉 = df_1분봉_대상.loc[idx_1분봉, '시가']
                            s_매수시점 = df_1분봉.loc[idx_1분봉, '시간']
                            n_매수가 = (n_시가_1분봉 if n_시가_1분봉 > n_매수기준가
                                     else n_매수기준가)
                            n_매수가 = self.tool.find_주문단가(n_기준가=n_매수가, n_틱보정=+2)
                            n_매수atr = n_직전atr
                            break

                    # 신호 업데이트
                    b_보유신호 = True if b_매수신호 else b_보유신호

            # 매도신호 확인
            if b_보유신호:
                # 매도기준가 생성
                n_매수후고가 = df_1분봉[(df_1분봉['시간'] > s_매수시점) & (df_1분봉['시간'] < s_분봉시간)]['고가'].max()
                n_매수후고가 = n_매수가 if pd.isna(n_매수후고가) else n_매수후고가
                # n_손절기준가 = n_매수가 - 2 * n_매수atr
                n_손절기준가 = n_매수가 - 1 * n_매수atr
                # n_목표기준가 = n_매수가 + 3 * n_직전atr
                # n_목표기준가 = n_매수가 + 4 * n_직전atr
                # n_목표기준가 = n_매수가 + 4 * n_매수atr
                n_목표기준가 = n_매수가 + 3 * n_매수atr
                # n_트레일링기준가 = n_매수후고가 - 2 * n_직전atr
                # n_트레일링기준가 = n_매수후고가 - 1 * n_직전atr
                n_트레일링기준가 = n_매수후고가 - 0.5 * n_직전atr

                # 1분봉 정보 필터링 - 3분봉 1개 봉, 매수 이후
                s_다음분봉시간 = min(시간 for 시간 in df_3분봉['시간'].values if 시간 > s_분봉시간)
                df_1분봉_대상 = (df_1분봉[(df_1분봉['시간'] >= s_분봉시간) & (df_1분봉['시간'] < s_다음분봉시간)
                                    & (df_1분봉['시간'] > s_매수시점)] if n_종가 > n_시가 else
                             df_1분봉[(df_1분봉['시간'] >= s_분봉시간) & (df_1분봉['시간'] < s_다음분봉시간)
                                    & (df_1분봉['시간'] >= s_매수시점)])
                if len(df_1분봉_대상) == 0: continue

                # 1분봉 정보 확인
                for idx_1분봉 in df_1분봉_대상.index:
                    # 기준정보 확인
                    s_분봉시간_1분봉 = df_1분봉_대상.loc[idx_1분봉, '시간']
                    n_경과시간 = (pd.Timestamp(s_분봉시간_1분봉) - pd.Timestamp(s_매수시점)).total_seconds() / 60
                    n_저가_1분봉 = df_1분봉_대상.loc[idx_1분봉, '저가']
                    n_고가_1분봉 = df_1분봉_대상.loc[idx_1분봉, '고가']
                    n_종가_1분봉 = df_1분봉_대상.loc[idx_1분봉, '종가']

                    # 매도신호 확인
                    b_손절터치 = n_저가_1분봉 < n_손절기준가
                    b_목표터치 = n_매수후고가 > n_목표기준가
                    b_트레일링 = n_저가_1분봉 < n_트레일링기준가 and b_목표터치
                    b_타임아웃 = s_분봉시간_1분봉 > '15:10:00'
                    b_매도신호 = b_손절터치 or b_트레일링 or b_타임아웃

                    # 매도정보 생성
                    if b_매도신호:
                        s_매도시점 = s_분봉시간_1분봉
                        s_매도가 =(n_손절기준가 if b_손절터치
                                else n_트레일링기준가 if b_트레일링
                                else n_종가_1분봉)
                        n_매도가 = self.tool.find_주문단가(n_기준가=s_매도가, n_틱보정=-3)

            # 결과 생성
            dic_매매정보 = dic_3분봉_시점
            dic_매매정보.update(당일고가=n_당일고가, 전일일봉고가=n_전일일봉고가,
                            돌파여부=b_돌파여부, 배열필터=b_배열필터, 시간필터=b_시간필터,
                            매수신호=b_매수신호,
                            매수시점=s_매수시점 if b_보유신호 else None,
                            매수가=n_매수가 if b_보유신호 else None,
                            매수atr=n_매수atr if b_보유신호 else None)
            dic_매매정보.update(손절기준가=n_손절기준가 if b_보유신호 else None,
                            목표기준가=n_목표기준가 if b_보유신호 else None,
                            트레일링기준가=n_트레일링기준가 if b_보유신호 else None,
                            손절터치=b_손절터치 if b_보유신호 else None,
                            목표터치=b_목표터치 if b_보유신호 else None,
                            트레일링=b_트레일링 if b_보유신호 else None,
                            타임아웃=b_타임아웃 if b_보유신호 else None,
                            매도신호=b_매도신호,
                            매도시점=s_매도시점 if b_매도신호 else None,
                            매도가=n_매도가 if b_매도신호 else None)
            dic_매매정보.update(보유신호=b_보유신호)

            # 결과 업데이트
            li_dic매매정보.append(dic_매매정보)

            # 신호 업데이트
            b_보유신호 = False if b_매도신호 else b_보유신호
            b_매수신호, b_매도신호 = False, False

        # 결과 정리
        df_매매정보 = pd.DataFrame(li_dic매매정보).sort_index()
        li_마지막컬럼 = ['매수신호', '매도신호', '보유신호', '매수시점', '매도시점', '매수가', '매도가']
        li_컬럼 = [컬럼 for 컬럼 in df_매매정보.columns if 컬럼 not in li_마지막컬럼] + li_마지막컬럼
        df_매매정보 = df_매매정보[li_컬럼]
        df_매매정보['수익률'] = (df_매매정보['매도가'] - df_매매정보['매수가']) / df_매매정보['매수가'] * 100 - 0.2

        # csv 저장
        os.makedirs(folder := os.path.join(f'{folder_타겟}_종목별', f'매매정보_{s_일자}'), exist_ok=True)
        df_매매정보.to_csv(os.path.join(folder, f'{file_타겟}_{s_일자}_{s_종목코드}_{s_종목명}.csv'),
                            index=False, encoding='cp949')

        return s_종목코드, df_매매정보


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def run():
    """ 실행 함수 """
    a = AnalyzerBot(n_검증일수=20, b_디버그모드=True)
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
