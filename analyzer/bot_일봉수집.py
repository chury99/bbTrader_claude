import os
import sys
import time

import pandas as pd
import re
from tqdm import tqdm

import ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyAttributeOutsideInit
class AnalyzerBot:
    # noinspection PyUnresolvedReferences
    def __init__(self):
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
        os.makedirs(self.folder_대상종목, exist_ok=True)
        os.makedirs(self.folder_조회순위, exist_ok=True)
        os.makedirs(self.folder_차트정보, exist_ok=True)

        # 추가 폴더 정의
        self.folder_spv2 = '/Users/ProjectWork/spTraderV2' if sys.platform == 'darwin'\
                    else 'E:/ProjectWork/spTraderV2' if sys.platform == 'win32' else ''

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.n_tr딜레이 = 0.2
        self.s_계좌번호 = str(dic_config['계좌번호'])

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)

        # 로그 기록
        self.make_로그(f'구동 시작')

    def get_대상종목(self):
        """ 분석 대상종목 데이터 확인하여 폴더에 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_spv2, '데이터', '대상종목')
        file_소스 = f'df_대상종목'
        folder_타겟 = self.folder_대상종목
        file_타겟 = f'df_대상종목'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 대상종목 파일 저장
        for s_일자 in li_대상일자:
            # 소스 데이터 읽어오기
            df_대상종목 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # 타겟 데이터 저장
            self.tool.df저장(df=df_대상종목, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(df_대상종목):,.0f}종목')

    def get_조회순위(self):
        """ 조회순위 데이터 확인하여 폴더에 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_spv2, '데이터', '조회순위_tr')
        file_소스 = f'df_조회순위'
        folder_타겟 = self.folder_조회순위
        file_타겟 = f'df_조회순위'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.csv' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 조회순위 파일 저장
        for s_일자 in li_대상일자:
            # 소스 데이터 읽어오기
            df_조회순위 = pd.read_csv(os.path.join(folder_소스, f'{file_소스}_{s_일자}.csv'),
                                  encoding='cp949', dtype=str, on_bad_lines='skip')

            # 타겟 데이터 저장
            self.tool.df저장(df=df_조회순위, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_종목수 = len(df_조회순위.dropna(subset='종목코드')['종목코드'].unique())
            self.make_로그(f'{s_일자} - {n_종목수:,.0f}종목')

    def get_일봉차트(self):
        """ 조회순위에 포함된 종목 대상으로 일봉 데이터 조회하여 pkl 파일로 저장 """
        # 기준정보 정의
        folder_소스 = self.folder_조회순위
        file_소스 = f'df_조회순위'
        folder_타겟 = self.folder_차트정보
        file_타겟 = f'dic_일봉차트'
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
            df_조회순위 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            li_대상종목 = sorted(종목.zfill(6) for 종목 in df_조회순위['종목코드'].dropna().unique())
            dic_코드2종목명 = df_조회순위.dropna(subset='종목코드').drop_duplicates('종목코드').set_index('종목코드')['종목명'].to_dict()
            dic_코드2종목명 = {key.zfill(6): value for key, value in dic_코드2종목명.items()}

            # 일봉차트 받아오기
            dic_일봉차트 = dict()
            for s_종목코드 in tqdm(li_대상종목, desc=f'일봉차트-{s_일자}', file=sys.stdout):
                # tr 조회
                df_일봉 = self.api.tr_주식일봉차트조회요청(s_종목코드=s_종목코드, s_종료일자=s_일자)
                time.sleep(self.n_tr딜레이)

                # 당일 데이터 미존재 시 처리
                if df_일봉.loc[df_일봉['일자'] == s_일자].empty: continue

                # 컬럼 정리
                df_일봉['종목명'] = dic_코드2종목명[s_종목코드]
                li_컬럼명_앞 = ['일자', '종목코드', '종목명']
                df_일봉 = df_일봉.loc[:, li_컬럼명_앞 + [컬럼 for 컬럼 in df_일봉.columns if 컬럼 not in li_컬럼명_앞]]

                # 데이터 정리 - 오름차순 정렬, 인덱스 설정
                df_일봉 = df_일봉.drop_duplicates().sort_values('일자')
                df_일봉['인덱스'] = pd.to_datetime(df_일봉['일자'], format='%Y%m%d')
                df_일봉 = df_일봉.set_index('인덱스')

                # 추가 데이터 생성 - 전일종가, 이동평균
                df_일봉['전일종가'] = df_일봉['종가'].shift(1)
                df_일봉['전일대비(%)'] = (df_일봉['종가'] / df_일봉['전일종가'] - 1) * 100
                df_일봉['종가ma5'] = df_일봉['종가'].rolling(5).mean()
                df_일봉['종가ma10'] = df_일봉['종가'].rolling(10).mean()
                df_일봉['종가ma20'] = df_일봉['종가'].rolling(20).mean()
                df_일봉['종가ma60'] = df_일봉['종가'].rolling(60).mean()
                df_일봉['종가ma120'] = df_일봉['종가'].rolling(120).mean()
                df_일봉['거래량ma5'] = df_일봉['거래량'].rolling(5).mean()
                df_일봉['거래량ma20'] = df_일봉['거래량'].rolling(20).mean()
                df_일봉['거래량ma60'] = df_일봉['거래량'].rolling(60).mean()
                df_일봉['거래량ma120'] = df_일봉['거래량'].rolling(120).mean()

                # dic에 추가
                dic_일봉차트[s_종목코드] = df_일봉[-120:]

            # 데이터 저장
            if len(dic_일봉차트) > 0:
                pd.to_pickle(dic_일봉차트, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(dic_일봉차트):,.0f}종목')


def run():
    """ 실행 함수 """
    a = AnalyzerBot()
    a.get_대상종목()
    a.get_조회순위()
    a.get_일봉차트()

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
