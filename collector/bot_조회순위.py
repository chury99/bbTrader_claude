import os
import sys
import time

import pandas as pd

import ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming
class CollectorBot:
    """ 장중 실시간 종목 조회순위 30초마다 수집 (spTraderV2 trader/bot_실시간수신 의 조회순위 저장부를 떼어 옴)

        · 매 분 1초·31초에 조회해서 당일 csv 에 이어 붙인다 - 같은 조회시각이 이미 있으면 건너뜀
        · 종료시각(config 의 종료시각)이 되면 끝낸다
        · 조회 실패는 기록만 하고 계속 돈다 - 수집 한 번 빠지는 게 모듈이 죽는 것보다 낫다
        · 실시간매매봇과 같은 키움 키를 쓰지만 30초에 1회라 호출 제한에 영향이 없다 """

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
        os.makedirs(self.folder_조회순위, exist_ok=True)

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.dt_종료시각 = pd.Timestamp(dic_config['종료시각'])
        self.s_계좌번호 = str(dic_config['계좌번호'])

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)

        # 로그 기록
        self.make_로그(f'구동 시작')

    def exec_조회순위수집(self):
        """ 종료시각까지 30초마다 조회순위 조회 후 저장 """
        # 기준정보 정의
        n_조회초 = None
        n_수집, n_실패 = 0, 0

        # 수집 루프
        while pd.Timestamp.now() < self.dt_종료시각:
            # 조회주기 확인 - 매 분 1초·31초, 같은 초에 한 번만
            dt_현재 = pd.Timestamp.now()
            n_초 = dt_현재.second
            if n_초 % 30 != 1 or n_조회초 == (dt_현재.hour, dt_현재.minute, n_초):
                time.sleep(0.2)
                continue
            n_조회초 = (dt_현재.hour, dt_현재.minute, n_초)

            # tr 조회 및 저장
            try:
                df_조회순위 = self.api.tr_실시간종목조회순위()
                if len(df_조회순위) > 0:
                    self._조회순위저장(df_조회순위=df_조회순위)
                    n_수집 += 1
            except Exception as e:
                n_실패 += 1
                if n_실패 <= 3 or n_실패 % 60 == 0:
                    self.make_로그(f'!!! 조회순위 조회 실패 {n_실패}회 - {type(e).__name__}: {e}')

            # 진행 기록 - 30분마다
            if dt_현재.minute % 30 == 0 and n_초 < 30:
                self.make_로그(f'수집 {n_수집}회 / 실패 {n_실패}회')

        # 로그 기록
        self.make_로그(f'종료시각 도달 - 수집 {n_수집}회 / 실패 {n_실패}회')

    def _조회순위저장(self, df_조회순위):
        """ 조회순위를 당일 csv 에 이어 붙여 저장 (spTraderV2 와 같은 형식) """
        # 기준 데이터 정의
        s_일자 = df_조회순위['일자'].values[0]
        s_시간 = df_조회순위['시간'].values[0]
        path_조회순위 = os.path.join(self.folder_조회순위, f'df_조회순위_{s_일자}.csv')

        # 기존 데이터에 동일 시간 존재 시 종료
        s_기존데이터 = open(path_조회순위, mode='rt', encoding='cp949').read() if os.path.exists(path_조회순위) else ''
        if s_시간 in s_기존데이터:
            return

        # df를 문자열로 변환
        li_조회순위 = [','.join(ary) for ary in df_조회순위.values.astype(str)]
        s_조회순위 = '\n'.join(li_조회순위) + '\n'
        s_컬럼명 = ','.join(df_조회순위.columns) + '\n'

        # 데이터 저장 - 기존 파일에 추가
        s_데이터 = s_조회순위 if os.path.exists(path_조회순위) else s_컬럼명 + s_조회순위
        with open(path_조회순위, mode='at', encoding='cp949') as f:
            f.write(s_데이터)


def run():
    """ 실행 함수 """
    c = CollectorBot()
    c.exec_조회순위수집()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
