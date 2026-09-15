import os
import sys
import re

import pandas as pd

import ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming
class CollectorBot:
    """ 장 시작 전 전체종목·조건검색·대상종목 수집 (spTraderV2 collector/bot_정보수집 에서 가져옴)

        · 조건검색은 키움에 저장해 둔 검색식 결과를 웹소켓으로 받는다 - 그 시각 결과만 받을 수 있어 매일 쌓는다
        · 대상종목 = 조건검색 중 '분석대상종목' 검색식 결과
        · 당일 파일이 이미 있으면 다시 받지 않는다 (장중 재구동 시 목록이 바뀌지 않게) """

    # noinspection PyUnresolvedReferences
    def __init__(self):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_collector')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보
        self.folder_전체종목 = dic_폴더정보['데이터|전체종목']
        self.folder_조건검색 = dic_폴더정보['데이터|조건검색']
        self.folder_대상종목 = dic_폴더정보['데이터|대상종목']
        os.makedirs(self.folder_전체종목, exist_ok=True)
        os.makedirs(self.folder_조건검색, exist_ok=True)
        os.makedirs(self.folder_대상종목, exist_ok=True)

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.s_계좌번호 = str(dic_config['계좌번호'])

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom, WebsocketAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)
        self.wsapi_모듈 = WebsocketAPI_kiwoom

        # 로그 기록
        self.make_로그(f'구동 시작')

    def get_전체종목(self):
        """ 코스피, 코스닥 전체 종목 조회하여 저장 """
        # 당일 파일 존재 시 통과
        path_전체종목 = os.path.join(self.folder_전체종목, f'df_전체종목_{self.s_오늘}')
        if os.path.exists(f'{path_전체종목}.pkl'):
            self.make_로그(f'{self.s_오늘} 이미 있음 - 통과')
            return

        # 데이터 받아오기
        li_df_전체종목 = list()
        for s_시장 in ['코스피', '코스닥']:
            df_종목 = self.api.tr_업종별주가요청(s_시장=s_시장)
            df_종목['시장'] = s_시장
            li_df_전체종목.append(df_종목)

        # 데이터 정리
        df_전체종목 = pd.concat(li_df_전체종목, axis=0).sort_values('종목코드')
        df_전체종목 = df_전체종목.loc[:, ['종목코드', '종목명', '시장']].reset_index(drop=True)

        # 데이터 저장
        self.tool.df저장(df=df_전체종목, path=path_전체종목)

        # 로그 기록
        df_코스피 = df_전체종목[df_전체종목['시장'] == '코스피']
        df_코스닥 = df_전체종목[df_전체종목['시장'] == '코스닥']
        self.make_로그(f'{self.s_오늘} 완료\n'
                     f' - {len(df_전체종목):,.0f} 종목 - 코스피 {len(df_코스피):,.0f}, 코스닥 {len(df_코스닥):,.0f}')

    def get_조건검색(self):
        """ 조건검색에 등록된 항목 조회하여 하나의 df로 저장 """
        # 당일 파일 존재 시 통과
        path_조건검색 = os.path.join(self.folder_조건검색, f'df_조건검색_{self.s_오늘}')
        if os.path.exists(f'{path_조건검색}.pkl'):
            self.make_로그(f'{self.s_오늘} 이미 있음 - 통과')
            return

        # 기준정보 불러오기
        df_전체종목 = pd.read_pickle(os.path.join(self.folder_전체종목, f'df_전체종목_{self.s_오늘}.pkl'))
        dic_코드2종목명 = df_전체종목.set_index('종목코드')['종목명'].to_dict()

        # 조건검색목록 확인 - 목록을 못 받으면 저장할 것이 없으므로 중단
        df_조검검색목록 = self.wsapi_모듈.SimpleWebsocketAPI().get_조건검색()
        if len(df_조검검색목록) == 0:
            raise RuntimeError('조건검색 목록 조회 실패 - 응답 없음')
        dic_번호2검색식명 = df_조검검색목록.set_index('검색식번호')['검색식명'].to_dict()

        # 데이터 받아오기
        li_df조건검색 = list()
        for s_검색식번호 in df_조검검색목록['검색식번호'].unique():
            # 검색식 조회 - 응답이 없어 건너뛴 검색식은 기록만 하고 다음으로
            api_조건검색 = self.wsapi_모듈.SimpleWebsocketAPI()
            df_검색종목 = api_조건검색.get_조건검색(n_검색식번호=int(s_검색식번호))
            if api_조건검색.b_응답없음:
                self.make_로그(f'!!! 조건검색 응답 없음 - {s_검색식번호} {dic_번호2검색식명[s_검색식번호]} '
                             f'({api_조건검색.N_응답제한초}초 초과, 건너뜀)')

            # 데이터 정리
            s_검색식명 = dic_번호2검색식명[s_검색식번호]
            b_데이터존재 = not df_검색종목.empty
            df_검색종목 = df_검색종목 if b_데이터존재 else pd.DataFrame()
            df_검색종목['종목코드'] = df_검색종목['종목코드'].str[1:]\
                                    if b_데이터존재 else [None]
            df_검색종목['종목명'] = df_검색종목['종목코드'].apply(lambda x: dic_코드2종목명[x] if x in dic_코드2종목명 else None)\
                                    if b_데이터존재 else None
            df_검색종목['검색식번호'] = s_검색식번호
            df_검색종목['검색식명'] = s_검색식명
            df_검색종목['조회일자'] = self.s_오늘
            df_검색종목['조회시간'] = pd.Timestamp.now().strftime('%H%M%S')

            # 데이터 정리
            df_검색종목 = df_검색종목[df_검색종목['종목명'].notna()] if b_데이터존재 else df_검색종목
            df_검색종목 = df_검색종목.sort_values('종목코드').reset_index(drop=True)

            # 데이터 추가
            li_df조건검색.append(df_검색종목)

        # 데이터 통합
        df_조건검색 = pd.concat(li_df조건검색, axis=0)
        if '분석대상종목' not in df_조건검색.loc[df_조건검색['종목명'].notna(), '검색식명'].values:
            self.make_로그(f'!!! 분석대상종목 결과 없음 - 대상종목이 빈 파일로 저장됨')

        # 데이터 저장
        self.tool.df저장(df=df_조건검색, path=path_조건검색)

        # 로그 기록
        self.make_로그(f'{self.s_오늘} 완료\n'
                     f' - {len(df_조건검색['검색식번호'].unique()):,.0f}개 검색식')

    def get_대상종목(self):
        """ 저장된 조건검색에서 대상종목 필터링 후 저장 """
        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(self.folder_조건검색) if '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(self.folder_대상종목) if '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 데이터 생성
        for s_일자 in li_대상일자:
            # 조건검색 불러오기
            df_조건검색 = pd.read_pickle(os.path.join(self.folder_조건검색, f'df_조건검색_{s_일자}.pkl'))

            # 대상종목 필터링
            df_대상종목 = df_조건검색[df_조건검색['검색식명'] == '분석대상종목'].sort_values('종목코드').reset_index(drop=True)

            # 데이터 저장
            self.tool.df저장(df=df_대상종목, path=os.path.join(self.folder_대상종목, f'df_대상종목_{s_일자}'))

            # 로그 기록
            self.make_로그(f'{s_일자} 완료\n'
                         f' - {len(df_대상종목):,.0f} 종목')


def run():
    """ 실행 함수 """
    c = CollectorBot()
    c.get_전체종목()
    c.get_조건검색()
    c.get_대상종목()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
