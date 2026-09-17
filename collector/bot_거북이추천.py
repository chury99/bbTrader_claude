import os
import sys

import pandas as pd

import ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming
class CollectorBot:
    """ 거북이 추천종목 카톡 발송 (spTraderV2 collector/bot_종목추천 find_거북이추천 에서 가져옴)

        · 당일 조회순위(장 시작~실행 시각)에 오른 종목 중 '거북이추천' 검색식 결과이면서 대상종목인 종목
        · 메세지 형식은 spTraderV2 와 같다
        · 당일 추천 파일이 이미 있으면 다시 보내지 않는다 (실행기 재구동 시 카톡 중복 방지) """

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
        self.folder_조회순위 = dic_폴더정보['데이터|조회순위_tr']
        self.folder_조건검색 = dic_폴더정보['데이터|조건검색']
        self.folder_대상종목 = dic_폴더정보['데이터|대상종목']
        self.folder_거북이추천 = os.path.join(dic_폴더정보['데이터|종목추천'], '거북이')
        os.makedirs(self.folder_거북이추천, exist_ok=True)

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def find_거북이추천(self):
        """ 조회순위 종목 중 거북이추천 종목에 포함된 종목 선정하여 저장 후 카톡 발송 """
        # 당일 파일 존재 시 통과
        path_추천종목 = os.path.join(self.folder_거북이추천, f'df_종목추천_거북이_{self.s_오늘}')
        if os.path.exists(f'{path_추천종목}.pkl'):
            self.make_로그(f'{self.s_오늘} 이미 있음 - 통과 (카톡 미발송)')
            return

        # 조회순위 불러오기
        df_조회순위 = pd.read_csv(os.path.join(self.folder_조회순위, f'df_조회순위_{self.s_오늘}.csv'),
                               encoding='cp949', dtype=str, on_bad_lines='skip')
        li_조회순위 = df_조회순위.dropna(subset='종목코드')['종목코드'].unique().tolist()

        # 거북이추천 불러오기
        df_조건검색 = pd.read_pickle(os.path.join(self.folder_조건검색, f'df_조건검색_{self.s_오늘}.pkl'))
        li_거북이추천 = df_조건검색[df_조건검색['검색식명'] == '거북이추천']['종목코드'].tolist()

        # 대상종목 불러오기 - 이상한 종목 제외용
        df_대상종목 = pd.read_pickle(os.path.join(self.folder_대상종목, f'df_대상종목_{self.s_오늘}.pkl'))
        li_대상종목 = df_대상종목['종목코드'].tolist()
        dic_코드2종목명 = df_대상종목.set_index('종목코드')['종목명'].to_dict()

        # 추천종목 생성
        li_추천종목 = [종목 for 종목 in li_조회순위 if 종목 in li_거북이추천 and 종목 in li_대상종목]
        li_dic추천종목 = [dict(일자=self.s_오늘, 종목코드=종목, 종목명=dic_코드2종목명[종목]) for 종목 in li_추천종목]
        df_추천종목 = pd.DataFrame(li_dic추천종목, columns=['일자', '종목코드', '종목명'])

        # 데이터 저장
        self.tool.df저장(df=df_추천종목, path=path_추천종목)

        # 카톡송부
        s_메세지 = f'## [{self.s_오늘}] 거북이 추천종목 {len(li_추천종목)}개 ##'
        for s_종목코드 in li_추천종목:
            s_메세지 = s_메세지 + f'\n  {dic_코드2종목명[s_종목코드]}({s_종목코드})'
        self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=s_메세지)

        # 로그 기록
        self.make_로그(f'{self.s_오늘} 완료\n'
                     f' - {len(df_추천종목):,.0f} 종목')


def run():
    """ 실행 함수 """
    c = CollectorBot()
    c.find_거북이추천()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
