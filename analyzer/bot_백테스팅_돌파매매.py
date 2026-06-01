import os
import sys
import json
import time
import re

import pandas as pd
import dataframe_image as dfi
from tqdm import tqdm
from google import genai

import analyzer, ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker
class AnalyzerBot:
    # noinspection PyUnresolvedReferences
    def __init__(self, n_검증일수):
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

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()
        # self.logic = analyzer.logic_백테스팅

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def pick_종목선정(self):
        """ 조회순위 데이터 기준으로 전일일봉 확인하여 대상종목 선정 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_서버, '데이터', '조회순위_tr')
        file_소스 = f'df_조회순위'
        folder_타겟 = os.path.join(self.folder_백테스팅, '10_종목선정')
        file_타겟 = f'df_종목선정'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.csv' in 파일)
        li_전체일자 = li_전체일자[-self.n_검증일수:]
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 조회순위 파일 저장
        for s_일자 in li_대상일자:
            # 소스 데이터 읽어오기
            df_조회순위 = pd.read_csv(os.path.join(folder_소스, f'{file_소스}_{s_일자}.csv'),
                                  encoding='cp949', dtype=str, on_bad_lines='skip')
            df_조회순위 = df_조회순위.loc[df_조회순위['종목코드'].notna(), ['일자', '종목코드', '종목명', '시간']]
            df_조회순위 = df_조회순위.drop_duplicates(subset='종목코드').sort_values('시간').reset_index(drop=True)

            # 추가 데이터 불러오기
            path_일봉 = os.path.join(self.folder_서버, '데이터', '차트캐시', '일봉1', f'dic_차트캐시_1일봉_{s_일자}.pkl')
            dic_일봉 = pd.read_pickle(path_일봉) if os.path.exists(path_일봉) else None
            path_대상종목 = os.path.join(self.folder_서버, '데이터', '대상종목', f'df_대상종목_{s_일자}.pkl')
            df_분석대상 = pd.read_pickle(path_대상종목) if os.path.exists(path_대상종목) else None
            if (dic_일봉 is None) or (df_분석대상 is None): continue

            # 대상종목 선정
            li_대상종목 = [종목 for 종목 in df_조회순위['종목코드'].unique() if 종목 in df_분석대상['종목코드'].values]

            # 종목별 데이터 생성
            li_dic종목선정 = list()
            for s_종목코드 in li_대상종목:
                # 기준정보 정의
                df_일봉 = dic_일봉.get(s_종목코드, None)
                if df_일봉 is None: continue
                idx_종목 = df_조회순위[df_조회순위['종목코드'] == s_종목코드].index[0]
                s_등장시간 = df_조회순위.loc[df_조회순위['종목코드'] == s_종목코드, '시간'].values[0]

                # 일봉 확인
                df_일봉 = df_일봉.copy()
                del df_일봉['전일종가']
                df_일봉['전일종가'] = df_일봉['종가'].shift(1)
                df_일봉['전일고가20'] = df_일봉['고가'].shift(2).rolling(20).max()
                df_일봉['전일상승률'] = df_일봉['전일대비(%)'].shift(1)
                df_일봉['전일돌파'] = (df_일봉['전일종가'] > df_일봉['전일고가20']) & (df_일봉['전일상승률'] < 29)
                df_일봉['전일ma5'] = df_일봉['종가ma5'].shift(1)
                df_일봉['전일ma20'] = df_일봉['종가ma20'].shift(1)
                df_일봉['전일ma120'] = df_일봉['종가ma120'].shift(1)
                df_일봉['전일정배열'] = (df_일봉['전일ma5'] > df_일봉['전일ma20']) & (df_일봉['전일ma20'] > df_일봉['전일ma120'])
                df_일봉['종목선정'] = df_일봉['전일돌파'] & df_일봉['전일정배열']
                df_일봉['당일상승'] = (df_일봉['전일대비(%)'] > 5) & df_일봉['종목선정']
                df_일봉['전일일봉고가'] = pd.concat([df_일봉['고가'].shift(1), df_일봉['전일고가20']], axis=1).max(axis=1)

                # 결과 생성
                dic_종목선정 = df_일봉.iloc[-1].to_dict()
                dic_종목선정.update(등장시간=s_등장시간)
                li_dic종목선정.append(dic_종목선정)

            # 데이터 정리
            df_종목선정 = pd.DataFrame(li_dic종목선정) if len(li_dic종목선정) > 0 else pd.DataFrame()

            # 결과 저장
            self.tool.df저장(df=df_종목선정, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_전체종목수 = len(df_종목선정)
            n_선정종목수 = len(df_종목선정[df_종목선정['종목선정']])
            n_상승종목수 = len(df_종목선정[df_종목선정['당일상승']])
            n_성공률 = n_상승종목수 / n_선정종목수 * 100 if n_선정종목수 != 0 else 0
            self.make_로그(f'{s_일자} - {n_상승종목수:,.0f} / {n_선정종목수:,.0f} / {n_전체종목수:,.0f}종목 - {n_성공률:,.0f}%')

    def make_신호생성(self):
        """ 선정된 종목에 대해 매수매도 신호 생성 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '10_종목선정')
        file_소스 = f'df_종목선정'
        folder_타겟 = os.path.join(self.folder_백테스팅, '20_신호생성')
        file_타겟 = f'dic_신호생성'
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

            # 추가정보 불러오기
            folder_3분봉 = os.path.join(self.folder_서버, '데이터', '차트캐시', '분봉3')
            li_파일 = sorted(파일 for 파일 in sorted(os.listdir(folder_3분봉))
                           if re.findall(r'\d{8}', 파일)[0] <= s_일자 and '.pkl' in 파일)
            dic_3분봉_전일 = pd.read_pickle(os.path.join(folder_3분봉, li_파일[-2])) if len(li_파일) >= 2 else dict()
            dic_3분봉_당일 = pd.read_pickle(os.path.join(folder_3분봉, li_파일[-1])) if len(li_파일) >= 1 else dict()
            dic_3분봉 = {종목코드: pd.concat([dic_3분봉_전일.get(종목코드, pd.DataFrame()), dic_3분봉_당일.get(종목코드, pd.DataFrame())])
                       for 종목코드 in dic_3분봉_당일.keys()}

            # 종목별 상승여부 확인
            dic_신호생성 = dict()
            for s_종목코드 in li_대상종목:
                # 기준정보 설정
                df_3분봉 = dic_3분봉.get(s_종목코드, None)
                if df_3분봉 is None: continue
                n_전일일봉고가 = df_종목선정.loc[s_종목코드, '전일일봉고가']
                s_등장시간 = df_종목선정.loc[s_종목코드, '등장시간']
                dt_등장시간 = pd.Timestamp(f'{s_일자} {s_등장시간}')

                # 지표 생성
                df_신호생성 = df_3분봉.copy().sort_index()
                df_신호생성['고가20'] = df_신호생성['고가'].shift(1).rolling(20).max()
                df_신호생성['저가20'] = df_신호생성['저가'].shift(1).rolling(20).min()
                df_신호생성['저가10'] = df_신호생성['저가'].shift(1).rolling(10).min()
                df_신호생성['tr'] = pd.concat([df_신호생성['고가'] - df_신호생성['저가'],
                                          (df_신호생성['고가'] - df_신호생성['종가'].shift(1)).abs(),
                                          (df_신호생성['저가'] - df_신호생성['종가'].shift(1)).abs()], axis=1).max(axis=1)
                df_신호생성['atr'] = df_신호생성['tr'].ewm(span=14, adjust=False).mean()
                df_3분봉_당일 = df_신호생성.loc[df_신호생성['일자'] == s_일자]
                df_신호생성['당일고가'] = [None] * (len(df_신호생성) - len(df_3분봉_당일)) + df_3분봉_당일['고가'].cummax().tolist()
                df_신호생성['당일저가'] = [None] * (len(df_신호생성) - len(df_3분봉_당일)) + df_3분봉_당일['저가'].cummin().tolist()
                df_신호생성['당일고가2atr'] = df_신호생성['당일고가'] - 2 * df_신호생성['atr']
                df_신호생성['당일고가3atr'] = df_신호생성['당일고가'] - 3 * df_신호생성['atr']
                df_신호생성['종가2atr'] = df_신호생성['종가'] - 2 * df_신호생성['atr']
                df_신호생성['전일일봉고가'] = n_전일일봉고가

                # 등장시간 반영
                df_신호생성 = df_신호생성.loc[df_신호생성.index >= dt_등장시간]
                df_신호생성['등장시간'] = s_등장시간

                # 매수신호 생성
                # df_신호생성['돌파신호'] = df_신호생성['고가'] > df_신호생성['고가20']
                # df_신호생성['돌파신호'] = ((df_신호생성['고가'] > df_신호생성['전일일봉고가'])
                #                    & (df_신호생성['고가'] == df_신호생성['당일고가']))
                # df_신호생성['돌파신호'] = ((df_신호생성['고가'] > df_신호생성['전일일봉고가'])
                #                    & (df_신호생성['고가'] <= df_신호생성['고가20']))
                # df_신호생성['돌파신호'] = ((df_신호생성['고가'] > df_신호생성['전일일봉고가'])
                #                    & (df_신호생성['고가'] > df_신호생성['고가20']))
                df_신호생성['돌파신호'] = ((df_신호생성['고가'] > df_신호생성['전일일봉고가'])
                                   & (df_신호생성['고가'] >= df_신호생성['당일고가']))
                df_신호생성['배열필터'] = df_신호생성['종가ma5'].shift(1) > df_신호생성['종가ma20'].shift(1)
                # df_신호생성['시간필터'] = df_신호생성['시간'] < '15:00:00'
                df_신호생성['시간필터'] = df_신호생성['시간'] < '13:00:00'
                df_신호생성['매수신호'] = df_신호생성['돌파신호'] & df_신호생성['배열필터'] & df_신호생성['시간필터']

                # 매도신호 생성
                df_신호생성['매수2atr'] = df_신호생성['종가2atr'].shift(1).where(df_신호생성['매수신호'], other=None).ffill()
                df_신호생성['매수저가20'] = df_신호생성['저가20'].shift(1).where(df_신호생성['매수신호'], other=None).ffill()
                df_신호생성['매수후고가'] = df_신호생성['고가'].groupby(df_신호생성['매수신호'].cumsum()).cummax()
                df_신호생성['매수후고가2atr'] = df_신호생성['매수후고가'] - 2 * df_신호생성['atr']
                df_신호생성['매수후고가3atr'] = df_신호생성['매수후고가'] - 3 * df_신호생성['atr']
                # df_신호생성['sl기준가'] = df_신호생성[['매수2atr', '당일저가', '매수저가20']].max(axis=1)
                # df_신호생성['ts기준가'] = df_신호생성[['당일고가2atr', '저가20']].max(axis=1)
                # df_신호생성['sl기준가'] = df_신호생성['저가20']
                # df_신호생성['ts기준가'] = df_신호생성['당일고가2atr']
                # df_신호생성['sl기준가'] = df_신호생성['저가20']
                # df_신호생성['ts기준가'] = df_신호생성['당일고가3atr']
                # df_신호생성['sl기준가'] = df_신호생성['매수저가20']
                # df_신호생성['ts기준가'] = df_신호생성['저가10']
                df_신호생성['sl기준가'] = df_신호생성['매수저가20']
                df_신호생성['ts기준가'] = df_신호생성['매수후고가2atr']   # 당일고가2atr이 아니라 매수이후고가2atr로 ts 설정
                # df_신호생성['sl기준가'] = df_신호생성['매수저가20']
                # df_신호생성['ts기준가'] = df_신호생성['매수후고가3atr']   # 당일고가2atr이 아니라 매수이후고가2atr로 ts 설정
                df_신호생성['손절신호'] = df_신호생성['저가'] < df_신호생성['sl기준가']
                df_신호생성['익절신호'] = df_신호생성['저가'] < df_신호생성['ts기준가']
                df_신호생성['타임아웃'] = df_신호생성['시간'] > '15:10:00'
                df_신호생성['매도신호'] = df_신호생성['익절신호'] | df_신호생성['손절신호'] | df_신호생성['타임아웃']

                # 보유신호 생성
                li_보유신호 = list()
                b_보유신호 = False
                for i in df_신호생성.index:
                    b_보유신호 = True if df_신호생성.loc[i, '매수신호'] else b_보유신호
                    li_보유신호.append(b_보유신호)
                    b_보유신호 = False if df_신호생성.loc[i, '매도신호'] else b_보유신호
                df_신호생성['보유신호'] = li_보유신호

                # 결과 정리
                li_마지막컬럼 = ['매수신호', '매도신호', '보유신호']
                li_컬럼명 = [컬럼 for 컬럼 in df_신호생성.columns if 컬럼 not in li_마지막컬럼] + li_마지막컬럼
                df_신호생성 = df_신호생성.loc[:, li_컬럼명]
                dic_신호생성[s_종목코드] = df_신호생성

            # 데이터 저장
            pd.to_pickle(dic_신호생성, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(dic_신호생성)}종목')

    def make_매수매도(self):
        """ 매수매도 신호의 틱정보 확인하여 매수가/매도가 확인 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '20_신호생성')
        file_소스 = f'dic_신호생성'
        folder_타겟 = os.path.join(self.folder_백테스팅, '30_매수매도')
        file_타겟 = f'dic_매수매도'
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
            dic_신호생성 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            li_대상종목 = list(dic_신호생성.keys())

            # 추가정보 불러오기
            path_체결 = os.path.join(self.folder_서버, '데이터', '주식체결_ws', f'주식체결_{s_일자}.csv')
            df_체결 = (pd.read_csv(path_체결, encoding='cp949', dtype=str, on_bad_lines='skip')
                       if os.path.exists(path_체결) else None)
            if df_체결 is None: continue
            df_체결['체결시간'] = df_체결['체결시간'].str[:2] + ':' + df_체결['체결시간'].str[2:4] + ':' + df_체결['체결시간'].str[4:]
            gr_체결 = df_체결.groupby('종목코드')

            # 종목별 매수매도 생성
            dic_매수매도 = dict()
            for s_종목코드 in li_대상종목:
                # 기준정보 설정
                df_매수매도 = dic_신호생성.get(s_종목코드, None).copy()
                if df_매수매도 is None: continue
                s_종목명 = df_매수매도['종목명'].values[0]
                df_체결 = gr_체결.get_group(s_종목코드).sort_values(['체결시간', '누적거래량'])
                dt_등장시간 = pd.Timestamp(f'{df_매수매도['일자'].values[0]} {df_매수매도['등장시간'].values[0]}')
                dt_퇴장시간 = pd.Timestamp(f'{df_매수매도['일자'].values[0]} {df_체결['체결시간'].max()}')

                # 매수매도 시점 확인
                df_매수매도['매수시점'] = df_매수매도['보유신호'] & ~df_매수매도['보유신호'].shift(1).fillna(False).astype(bool)
                df_매수매도['매도시점'] = (~df_매수매도['보유신호'] & df_매수매도['보유신호'].shift(1).fillna(False)).shift(-1).astype(bool)
                df_매수매도.loc[df_매수매도.index[-1], '매도시점'] = False

                # 매수정보 생성
                li_매수시점 = list()
                li_매수가 = list()
                for dt in df_매수매도.index:
                    s_매수시점, n_매수가 = None, None
                    b_매수시점 = df_매수매도.loc[dt, '매수시점']
                    if b_매수시점 and dt_등장시간 <= dt <= dt_퇴장시간:
                        s_매수봉시간 = df_매수매도.loc[dt, '시간']
                        n_고가20 = df_매수매도.loc[dt, '고가20']
                        df_체결_시점 = df_체결.loc[df_체결['체결시간'] >= s_매수봉시간]
                        for idx in df_체결_시점.index:
                            s_체결시간 = df_체결_시점.loc[idx, '체결시간']
                            n_현재가 = int(df_체결_시점.loc[idx, '현재가'][1:])
                            if n_현재가 > n_고가20:
                                s_매수시점 = s_체결시간
                                n_매수가 = self.tool.find_주문단가(n_기준가=n_현재가, n_틱보정=+3)
                                break
                    li_매수시점.append(s_매수시점)
                    li_매수가.append(n_매수가)

                # 매수정보 정리
                df_매수매도['매수시점'] = li_매수시점
                df_매수매도['매수가'] = li_매수가
                df_매수매도['매수시점'] = df_매수매도['매수시점'].ffill().where(df_매수매도['보유신호'])
                df_매수매도['매수가'] = df_매수매도['매수가'].ffill().where(df_매수매도['보유신호'])

                # 매도정보 생성
                li_매도시점 = list()
                li_매도가 = list()
                for dt in df_매수매도.index:
                    s_매도시점, n_매도가 = None, None
                    b_매도시점 = df_매수매도.loc[dt, '매도시점']
                    if b_매도시점 and dt_등장시간 <= dt <= dt_퇴장시간 and df_매수매도.loc[dt, '매수시점'] is not None:
                        s_매수시간 = max(df_매수매도.loc[dt, '시간'], df_매수매도.loc[dt, '매수시점'])
                        n_손절기준가 = df_매수매도.loc[dt, 'sl기준가']
                        n_익절기준가 = df_매수매도.loc[dt, 'ts기준가']
                        df_체결_시점 = df_체결.loc[df_체결['체결시간'] >= s_매수시간]
                        for idx in df_체결_시점.index:
                            s_체결시간 = df_체결_시점.loc[idx, '체결시간']
                            n_현재가 = int(df_체결_시점.loc[idx, '현재가'][1:])
                            if n_현재가 < max(n_손절기준가, n_익절기준가):
                                s_매도시점 = s_체결시간
                                n_매도가 = self.tool.find_주문단가(n_기준가=n_현재가, n_틱보정=-3)
                                break
                    li_매도시점.append(s_매도시점)
                    li_매도가.append(n_매도가)

                # 매도정보 정리
                df_매수매도['매도시점'] = li_매도시점
                df_매수매도['매도가'] = li_매도가

                # 수익률 정리
                df_매수매도['수익률'] = (df_매수매도['매도가'] / df_매수매도['매수가'] - 1) * 100 - 0.2

                # df 추가
                dic_매수매도[s_종목코드] = df_매수매도

                # df 저장
                folder = os.path.join(f'{folder_타겟}_종목별', f'매수매도_{s_일자}')
                os.makedirs(folder, exist_ok=True)
                df_매수매도.to_csv(os.path.join(folder, f'df_매수매도_{s_일자}_{s_종목코드}_{s_종목명}.csv'),
                               index=False, encoding='cp949')

            # 데이터 저장
            pd.to_pickle(dic_매수매도, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(dic_매수매도)}종목')

    def make_손익정리(self):
        """ 매수매도 결과를 바탕으로 손익 정리 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '30_매수매도')
        file_소스 = f'dic_매수매도'
        folder_타겟 = os.path.join(self.folder_백테스팅, '40_손익정리')
        file_타겟 = f'df_손익정리'
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
            dic_매수매도 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            li_대상종목 = list(dic_매수매도.keys())

            # 손익정리
            li_dic손익정리 = list()
            for s_종목코드 in li_대상종목:
                # 기준정보 설정
                df_매수매도 = dic_매수매도.get(s_종목코드, None)
                if df_매수매도 is None: continue
                s_종목명 = df_매수매도['종목명'].values[0]

                # 손익정리 생성
                df_매매결과 = df_매수매도.loc[df_매수매도['매도시점'].notnull()]
                for idx in df_매매결과.index:
                    li_컬럼 = ['일자', '종목코드', '종목명',
                             '매수신호', '매도신호', '손절신호', '익절신호', '타임아웃',
                             '보유신호', '매수시점', '매도시점', '매수가', '매도가', '수익률']
                    dic_손익정리 = df_매매결과.loc[idx, li_컬럼].to_dict()
                    li_dic손익정리.append(dic_손익정리)

            # df 생성
            df_손익정리 = pd.DataFrame(li_dic손익정리) if len(li_dic손익정리) > 0 else pd.DataFrame()
            df_손익정리 = df_손익정리.sort_values('매수시점') if not df_손익정리.empty else df_손익정리

            # 데이터 저장
            self.tool.df저장(df=df_손익정리, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 지표 정의
            df_손익정리_수익 = df_손익정리.loc[df_손익정리['수익률'] > 0] if not df_손익정리.empty else pd.DataFrame()
            df_손익정리_손실 = df_손익정리.loc[df_손익정리['수익률'] <= 0] if not df_손익정리.empty else pd.DataFrame()
            n_총매매 = len(df_손익정리)
            n_수익매매 = len(df_손익정리_수익)
            n_손실매매 = len(df_손익정리_손실)
            n_승률 = n_수익매매 / n_총매매 * 100 if n_총매매 > 0 else 0
            n_총손익률 = df_손익정리['수익률'].sum() if n_총매매 > 0 else 0
            n_평균수익률 = df_손익정리_수익['수익률'].mean() if n_수익매매 > 0 else 0
            n_평균손실률 = df_손익정리_손실['수익률'].mean() if n_손실매매 > 0 else 0
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
        folder_소스 = os.path.join(self.folder_백테스팅, '40_손익정리')
        file_소스 = f'df_손익정리'
        folder_타겟 = os.path.join(self.folder_백테스팅, '50_결과정리')
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
            li_df전체손익 = list()
            for s_파일일자 in li_파일일자:
                # 기준정보 정의
                df_손익정리 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_파일일자}.pkl'))
                if df_손익정리.empty: continue

                # 지표 생성
                df_손익정리_수익 = df_손익정리.loc[df_손익정리['수익률'] > 0]
                df_손익정리_손실 = df_손익정리.loc[df_손익정리['수익률'] <= 0]
                n_총매매 = len(df_손익정리)
                n_수익매매 = len(df_손익정리_수익)
                n_손실매매 = len(df_손익정리_손실)
                n_승률 = n_수익매매 / n_총매매 * 100 if n_총매매 > 0 else 0
                n_총손익률 = df_손익정리['수익률'].sum() if n_총매매 > 0 else 0
                n_평균수익률 = df_손익정리_수익['수익률'].mean() if n_수익매매 > 0 else 0
                n_평균손실률 = df_손익정리_손실['수익률'].mean() if n_손실매매 > 0 else 0
                n_손익비 = n_평균수익률 / abs(n_평균손실률) if n_평균손실률 != 0 else 0
                n_기대치 = (n_승률 / 100 * n_손익비) - (1 - n_승률 / 100)

                # 결과 생성
                dic_결과정리 = dict(일자=s_파일일자,
                                총매매=n_총매매, 수익매매=n_수익매매, 손실매매=n_손실매매, 승률=n_승률,
                                총손익률=n_총손익률, 평균수익률=n_평균수익률, 평균손실률=n_평균손실률, 손익비=n_손익비,
                                기대치=n_기대치)
                li_dic결과정리.append(dic_결과정리)
                li_df전체손익.append(df_손익정리)

            # df 생성
            df_결과정리 = pd.DataFrame(li_dic결과정리).sort_values('일자') if len(li_dic결과정리) > 0 else pd.DataFrame()
            df_전체손익 = pd.concat(li_df전체손익) if len(li_df전체손익) > 0 else pd.DataFrame()

            # 데이터 저장
            self.tool.df저장(df=df_결과정리, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 지표 정의
            df_전체손익_수익 = df_전체손익.loc[df_전체손익['수익률'] > 0]
            df_전체정리_손실 = df_전체손익.loc[df_전체손익['수익률'] <= 0]
            n_총매매 = len(df_전체손익)
            n_수익매매 = len(df_전체손익_수익)
            n_손실매매 = len(df_전체정리_손실)
            n_승률 = n_수익매매 / n_총매매 * 100 if n_총매매 > 0 else 0
            n_총손익률 = df_전체손익['수익률'].sum() if n_총매매 > 0 else 0
            n_평균수익률 = df_전체손익_수익['수익률'].mean() if n_수익매매 > 0 else 0
            n_평균손실률 = df_전체정리_손실['수익률'].mean() if n_손실매매 > 0 else 0
            n_손익비 = n_평균수익률 / abs(n_평균손실률) if n_평균손실률 != 0 else 0
            n_기대치 = (n_승률 / 100 * n_손익비) - (1 - n_승률 / 100)

            # 로그 기록
            n_누적일수 = len(df_결과정리)
            self.make_로그(f'{s_일자}({n_누적일수}일)\n'
                         f' - 누적기대치 {n_기대치:,.2f}, 누적수익 {n_총손익률:,.0f}%\n'
                         f' - 누적승률 {n_승률:,.0f}% (총 {n_총매매}, 승 {n_수익매매}, 패 {n_손실매매})\n'
                         f' - 누적손익비 {n_손익비:,.1f} (평균수익 {n_평균수익률:,.0f}%, 평균손실 {n_평균손실률:,.0f}%)')


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def run():
    """ 실행 함수 """
    a = AnalyzerBot(n_검증일수=20)
    a.pick_종목선정()
    a.make_신호생성()
    a.make_매수매도()
    a.make_손익정리()
    a.make_결과정리()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
