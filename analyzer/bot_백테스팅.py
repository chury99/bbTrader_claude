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
    def __init__(self, s_전략명, n_조회순위일수):
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
        self.folder_대상종목 = dic_폴더정보['데이터|대상종목']
        self.folder_조회순위 = dic_폴더정보['데이터|조회순위']
        self.folder_차트정보 = dic_폴더정보['데이터|차트정보']
        self.folder_분석 = dic_폴더정보['분석']
        self.folder_백테스팅 = os.path.join(dic_폴더정보['분석|백테스팅'], f'{s_전략명}_{n_조회순위일수}')
        os.makedirs(self.folder_백테스팅, exist_ok=True)

        # 추가 폴더 정의
        self.folder_spv2 = ('/Users/ProjectWork/spTraderV2' if sys.platform == 'darwin' else
                            'E:/ProjectWork/spTraderV2' if sys.platform == 'win32' else '')
        self.folder_서버 = ('/Volumes/extSSD4tb/80_Backup/10_python_backup/ProjectWork/spTraderV2'
                          if sys.platform == 'darwin' else '')

        # 추가 폴더 정의
        # dic_aikey = json.load(open(os.path.join(dic_config['folder_aikey'], 'aikey.json')))
        # self.api키_gemini = dic_aikey.get('gemini', dict()).get('apikey', None)
        # self.n_서버파일보관일수 = int(dic_config['파일보관기간(일)_analyzer'])

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        # self.n_tr딜레이 = 0.2
        # self.s_계좌번호 = str(dic_config['계좌번호'])
        self.s_전략명 = s_전략명
        self.n_조회순위일수 = n_조회순위일수

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()
        self.logic = analyzer.logic_백테스팅

        # 키움 API 연결
        # sys.path.append(dic_config['folder_kiwoom'])
        # import RestAPI_kiwoom
        # self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def get_조회순위(self):
        """ 조회순위 데이터 확인하여 폴더에 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_서버, '데이터', '조회순위_tr')
        file_소스 = f'df_조회순위'
        folder_타겟 = os.path.join(self.folder_백테스팅, '10_조회순위')
        file_타겟 = f'df_조회순위'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        folder_전체일자 = os.path.join(self.folder_spv2, '데이터', '조회순위_tr')
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_전체일자)
                         if file_소스 in 파일 and '.csv' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]
        li_대상일자 = li_대상일자 + [self.s_오늘] if self.s_오늘 not in li_대상일자 else li_대상일자

        # 기준정보 정의
        # n_조회순위일수 = (1 if self.s_전략명 == '눌림목기본' else None)
        # if n_조회순위일수 is None: raise

        # 조회순위 파일 저장
        for s_일자 in li_대상일자:
            # 소스 데이터 읽어오기
            li_파일명 = sorted(파일 for 파일 in os.listdir(folder_소스)
                            if file_소스 in 파일 and '.csv' in 파일 and re.findall(r'\d{8}', 파일)[0] <= s_일자)
            li_df조회순위 = [pd.read_csv(os.path.join(folder_소스, 파일), encoding='cp949', dtype=str, on_bad_lines='skip')
                         for 파일 in sorted(li_파일명)[-self.n_조회순위일수:]]
            df_조회순위 = pd.concat(li_df조회순위, ignore_index=True)
            # df_조회순위 = pd.read_csv(os.path.join(folder_소스, f'{file_소스}_{s_일자}.csv'),
            #                       encoding='cp949', dtype=str, on_bad_lines='skip')

            # 데이터 정리
            df_조회순위 = df_조회순위.loc[df_조회순위['종목코드'].notna(), ['일자', '종목코드', '종목명']].copy()
            df_조회순위 = df_조회순위.drop_duplicates().sort_values(['일자', '종목코드']).reset_index(drop=True)

            # 타겟 데이터 저장
            self.tool.df저장(df=df_조회순위, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_종목수 = len(df_조회순위['종목코드'].unique())
            self.make_로그(f'{self.s_전략명}_{self.n_조회순위일수} - {s_일자} - {n_종목수:,.0f}종목')

    def make_지표생성(self):
        """ 일봉 데이터 기반으로 지표 생성 후 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '10_조회순위')
        file_소스 = f'df_조회순위'
        folder_타겟 = os.path.join(self.folder_백테스팅, '20_지표생성')
        file_타겟 = f'dic_지표생성'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 지표 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            df_조회순위 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            # dic_코드2종목명 = df_조회순위.set_index('종목코드').to_dict()['종목명']

            # 추가 데이터 불러오기
            path_대상종목 = os.path.join(self.folder_대상종목, f'df_대상종목_{s_일자}.pkl')
            path_일봉 = os.path.join(self.folder_spv2, '데이터', '차트캐시', '일봉1', f'dic_차트캐시_1일봉_{s_일자}.pkl')
            df_분석대상 = pd.read_pickle(path_대상종목) if os.path.exists(path_대상종목) else None
            dic_일봉 = pd.read_pickle(path_일봉) if os.path.exists(path_일봉) else None
            if (df_분석대상 is None) or (dic_일봉 is None): continue

            # 대상종목 선정
            # li_대상종목 = sorted(종목 for 종목 in dic_일봉차트.keys() if 종목 in df_분석대상['종목코드'].values)
            li_대상종목 = sorted(종목 for 종목 in df_조회순위['종목코드'].unique() if 종목 in df_분석대상['종목코드'].values)

            # 종목별 데이터 생성
            dic_지표생성 = dict()
            for s_종목코드 in li_대상종목:
                # 기준정보 정의
                df_일봉 = dic_일봉.get(s_종목코드, pd.DataFrame())
                if df_일봉.empty: continue
                s_종목명 = df_일봉['종목명'].values[0]

                # 지표 생성
                df_일봉['바디'] = (df_일봉['종가'] - df_일봉['시가']) / df_일봉['전일종가'] * 100
                df_일봉['전일고가3봉'] = df_일봉['고가'].shift(1).rolling(window=3).max()
                df_일봉['전일고가14봉'] = df_일봉['고가'].shift(1).rolling(window=14).max()
                df_일봉['전일바디50'] = 0.5 * (df_일봉['종가'].shift(1) - df_일봉['시가'].shift(1)) + df_일봉['시가'].shift(1)

                # 신호생성
                df_일봉['돌파신호'] = df_일봉['종가'] > df_일봉['전일고가3봉']
                df_일봉['배열신호'] = (df_일봉['종가'] > df_일봉['종가ma60']) & (df_일봉['종가ma60'] > df_일봉['종가ma120'])
                df_일봉['눌림신호'] = (-2 < df_일봉['바디']) & (df_일봉['바디'] < 5)
                df_일봉['매미신호'] = (df_일봉['전일바디50'] < df_일봉['종가']) & (df_일봉['종가'] <= df_일봉['고가'].shift(1))

                # 결과 생성
                df_일봉['고가상승률'] = (df_일봉['고가'] / df_일봉['전일종가'] - 1) * 100
                df_일봉['익일상승여부'] = df_일봉['고가상승률'].shift(-1) > 10

                # df 추가
                dic_지표생성[s_종목코드] = df_일봉

                # df 저장
                folder = os.path.join(f'{folder_타겟}_종목별', f'지표생성_{s_일자}')
                os.makedirs(folder, exist_ok=True)
                df_일봉.to_csv(os.path.join(folder, f'df_지표생성_{s_일자}_{s_종목코드}_{s_종목명}.csv'),
                             index=False, encoding='cp949')

            # 결과 저장
            pd.to_pickle(dic_지표생성, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 로그 기록
            self.make_로그(f'{self.s_전략명}_{self.n_조회순위일수} - {s_일자} - {len(dic_지표생성):,.0f}종목')

    def make_지표생성_학습용(self):
        """ 지표생성 데이터 기준으로 마지막 일자 데이터에 대한 상승여부 확인 후 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '20_지표생성')
        file_소스 = f'dic_지표생성'
        folder_타겟 = os.path.join(self.folder_백테스팅, '20_지표생성_학습용')
        file_타겟 = f'df_학습용지표'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 지표 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기
            dic_지표생성 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # 추가 데이터 불러오기 - 다음날 일봉
            folder_일봉 = os.path.join(self.folder_spv2, '데이터', '차트캐시', '일봉1')
            li_일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_일봉) if '.pkl' in 파일
                     and re.findall(r'\d{8}', 파일)[0] > s_일자]
            if len(li_일자) == 0: continue
            s_익일 = min(li_일자)
            dic_익일일봉 = pd.read_pickle(os.path.join(folder_일봉, f'dic_차트캐시_1일봉_{s_익일}.pkl'))

            # 종목별 데이터 생성
            li_dic학습용지표 = list()
            for s_종목코드, df_지표생성 in dic_지표생성.items():
                # 기준정보 정의
                dt_당일 = pd.Timestamp(s_일자)
                dt_익일 = pd.Timestamp(s_익일)
                df_익일일봉 = dic_익일일봉.get(s_종목코드, pd.DataFrame())
                if df_익일일봉.empty or dt_익일 not in df_익일일봉.index: continue

                # 데이터 확인
                n_익일고가상승률 = (df_익일일봉.loc[dt_익일, '고가'] / df_익일일봉.loc[dt_익일, '전일종가'] - 1) * 100
                b_익일상승여부 = n_익일고가상승률 > 10

                # 결과 생성
                dic_학습용지표 = df_지표생성.loc[dt_당일].to_dict()
                dic_학습용지표.update(익일상승여부=b_익일상승여부, 익일고가상승률=n_익일고가상승률)

                # 결과 추가
                li_dic학습용지표.append(dic_학습용지표)

            # 데이터 정리
            df_학습용지표 = pd.DataFrame(li_dic학습용지표) if len(li_dic학습용지표) > 0 else pd.DataFrame()

            # 결과 저장
            self.tool.df저장(df=df_학습용지표, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_전체종목수 = len(df_학습용지표)
            n_선정종목수 = len(df_학습용지표.loc[df_학습용지표['익일상승여부']])
            self.make_로그(f'{self.s_전략명}_{self.n_조회순위일수} - {s_일자} - {n_선정종목수:,.0f}/{n_전체종목수:,.0f}종목')

    def pick_종목선정(self):
        """ 종목선정 기준에 따라 추천종목 선정 후 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '20_지표생성')
        file_소스 = f'dic_지표생성'
        folder_타겟 = os.path.join(self.folder_백테스팅, '30_종목선정')
        file_타겟 = f'df_종목선정'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 조회순위 종목 기준의 일봉차트 데이터
            dic_지표생성 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # 종목별 선정조건 확인
            li_dic종목선정 = list()
            for s_종목코드, df_일봉 in dic_지표생성.items():
                # 조건 확인
                dic_종목선정 = (self.logic.judge_눌림목기본(df_일봉=df_일봉) if self.s_전략명 == '눌림목기본' else
                            self.logic.judge_눌림목매미(df_일봉=df_일봉) if self.s_전략명 == '눌림목매미' else
                            self.logic.judge_조건확인(df_일봉=df_일봉) if self.s_전략명 == '조건확인' else
                            self.logic.judge_클로드20260519(df_일봉=df_일봉) if self.s_전략명 == '클로드20260519' else
                            None)
                if dic_종목선정 is None: raise
                if len(dic_종목선정) == 0: continue

                # 결과 추가
                li_dic종목선정.append(dic_종목선정)

            # 데이터 정리
            df_종목선정 = pd.DataFrame(li_dic종목선정) if len(li_dic종목선정) > 0 else pd.DataFrame()

            # 결과 저장
            self.tool.df저장(df=df_종목선정, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            df_상승후보 = df_종목선정.loc[df_종목선정['종목선정']].copy().reset_index(drop=True)
            n_전체종목수 = len(df_종목선정)
            n_선정종목수 = len(df_상승후보)
            s_로그 = f'{self.s_전략명}_{self.n_조회순위일수} - {s_일자} - {n_선정종목수:,.0f}/{n_전체종목수:,.0f}종목'
            for idx in df_상승후보.index:
                s_로그 = s_로그 + f'\n  {s_일자} - {idx + 1} - {df_상승후보.loc[idx, '종목명']}({df_상승후보.loc[idx, '종목코드']})'
            self.make_로그(s_로그)

    def make_상승여부(self):
        """ 선정된 종목에 대해 익일 상승 여부 확인 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '30_종목선정')
        file_소스 = f'df_종목선정'
        folder_타겟 = os.path.join(self.folder_백테스팅, '40_상승여부')
        file_타겟 = f'df_상승여부'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 전일 기준
            li_파일명 = [파일 for 파일 in os.listdir(folder_소스) if 파일 < f'{file_소스}_{s_일자}.pkl' and 'pkl' in 파일]
            if len(li_파일명) == 0: continue
            df_종목선정_전일 = pd.read_pickle(os.path.join(folder_소스, max(li_파일명)))
            li_대상종목_전일 = df_종목선정_전일.loc[df_종목선정_전일['종목선정'], '종목코드'].to_list()
            # dic_코드2종목명 = df_종목선정_전일.set_index('종목코드')['종목명'].to_dict()

            # 추가정보 불러오기
            folder_일봉 = os.path.join(self.folder_spv2, '데이터', '차트캐시', '일봉1')
            dic_일봉 = pd.read_pickle(os.path.join(folder_일봉, f'dic_차트캐시_1일봉_{s_일자}.pkl'))

            # 종목별 상승여부 확인
            li_dic상승여부 = list()
            for s_종목코드 in li_대상종목_전일:
                # 기준정보 설정
                df_일봉 = dic_일봉.get(s_종목코드, pd.DataFrame())
                if df_일봉.empty: continue

                # 데이터 확인
                dt_당일 = df_일봉.index[-1]
                dt_전일 = df_일봉.index[-2]
                s_종목명 = df_일봉.loc[dt_당일, '종목명']
                n_전일종가 = df_일봉.loc[dt_전일, '종가']
                n_당일고가 = df_일봉.loc[dt_당일, '고가']
                n_당일저가 = df_일봉.loc[dt_당일, '저가']
                n_당일고가율 = (n_당일고가 / n_전일종가 - 1) * 100
                n_당일저가율 = (n_당일저가 / n_전일종가 - 1) * 100
                b_상승여부 = n_당일고가율 > 10

                # 결과 생성
                dic_상승여부 = dict(일자=s_일자, 종목코드=s_종목코드, 종목명=s_종목명,
                                전일종가=n_전일종가, 당일고가=n_당일고가, 당일저가=n_당일저가,
                                당일고가율=n_당일고가율, 당일저가율=n_당일저가율, 상승여부=b_상승여부)
                li_dic상승여부.append(dic_상승여부)

            # 데이터 정리
            df_상승여부 = pd.DataFrame(li_dic상승여부) if len(li_dic상승여부) > 0 else pd.DataFrame()

            # 데이터 저장
            self.tool.df저장(df=df_상승여부, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_대상종목수 = len(df_상승여부)
            n_상승종목수 = len(df_상승여부.loc[df_상승여부['상승여부']]) if not df_상승여부.empty else 0
            n_승률 = n_상승종목수 / n_대상종목수 * 100 if n_대상종목수 > 0 else 0
            self.make_로그(f'{self.s_전략명}_{self.n_조회순위일수} - {s_일자} - 승률 {n_승률:.0f}%({n_상승종목수:,.0f}/{n_대상종목수:,.0f})')

    def make_결과확인(self):
        """ 일별 승률 확인 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_백테스팅, '40_상승여부')
        file_소스 = f'df_상승여부'
        folder_타겟 = os.path.join(self.folder_백테스팅, '50_결과확인')
        file_타겟 = f'df_결과확인'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 전체 파일 읽어오기
            # li_df상승여부 = [pd.read_pickle(os.path.join(folder_소스, 파일)) for 파일 in sorted(os.listdir(folder_소스))
            #              if file_소스 in 파일 and '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] <= s_일자]
            li_파일명 = [파일 for 파일 in sorted(os.listdir(folder_소스))
                         if file_소스 in 파일 and '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] <= s_일자]
            dic_상승여부 = {re.findall(r'\d{8}', 파일)[0]: pd.read_pickle(os.path.join(folder_소스, 파일))
                        for 파일 in li_파일명}

            # 결과정리
            li_dic결과확인 = list()
            # for df_상승여부 in li_df상승여부:
            for s_데이터일자, df_상승여부 in dic_상승여부.items():
                # 데이터 생성
                # s_데이터일자 = df_상승여부['일자'].values[0]
                # s_데이터일자 = max(일자 for 일자 in li_전체일자 if 일자 < s_일자)
                n_대상종목수 = len(df_상승여부)
                n_상승종목수 = len(df_상승여부.loc[df_상승여부['상승여부']]) if not df_상승여부.empty else 0
                n_승률 = n_상승종목수 / n_대상종목수 * 100 if n_대상종목수 > 0 else 0

                # 결과 확인
                dic_결과확인 = dict(일자=s_데이터일자, 대상종목수=n_대상종목수, 상승종목수=n_상승종목수, 승률=n_승률)
                li_dic결과확인.append(dic_결과확인)

            # 데이터 정리
            df_결과확인 = pd.DataFrame(li_dic결과확인).sort_values('일자') if len(li_dic결과확인) > 0 else pd.DataFrame()
            df_결과확인['누적대상'] = df_결과확인['대상종목수'].cumsum()
            df_결과확인['누적상승'] = df_결과확인['상승종목수'].cumsum()
            df_결과확인['누적승률'] = df_결과확인['누적상승'] / df_결과확인['누적대상'] * 100

            # 데이터 저장
            self.tool.df저장(df=df_결과확인, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_누적대상 = df_결과확인['누적대상'].values[-1]
            n_누적상승 = df_결과확인['누적상승'].values[-1]
            n_누적승률 = df_결과확인['누적승률'].values[-1]
            self.make_로그(f'{self.s_전략명}_{self.n_조회순위일수} - {s_일자} - 누적승률 {n_누적승률:.0f}%({n_누적상승:,.0f}/{n_누적대상:,.0f})')


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def run():
    """ 실행 함수 """
    # li_전략명 = ['조건확인', '눌림목기본', '눌림목매미']
    li_전략명 = ['클로드20260519']
    # li_조회순위일수 = [5, 4, 3, 2, 1]
    li_조회순위일수 = [1]
    for s_전략명 in li_전략명:
        for n_조회순위일수 in li_조회순위일수:
            a = AnalyzerBot(s_전략명=s_전략명, n_조회순위일수=n_조회순위일수)
            a.get_조회순위()
            a.make_지표생성()
            a.make_지표생성_학습용()
            a.pick_종목선정()
            a.make_상승여부()
            a.make_결과확인()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
