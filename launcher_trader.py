import os
import sys
# import json
import time

import pandas as pd
import multiprocessing as mp

import trader, ut


# noinspection NonAsciiCharacters,PyPep8Naming,SpellCheckingInspection,PyUnreachableCode
class LauncherTrader:
    # noinspection PyUnresolvedReferences
    def __init__(self):
        # config 읽어 오기
        self.folder_프로젝트 = os.path.dirname(os.path.abspath(__file__))
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_trader')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.s_종료시각 = dic_config['종료시각']

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def run_트레이더(self):
        """ 트레이딩을 위한 bot 실행 """
        # 프로세스 생성 및 실행
        dic_매매봇 = dict(s_타겟=trader.bot_트레이딩.run, s_네임='봉봉trader')
        p_매매봇 = mp.Process(target=dic_매매봇['s_타겟'], name=dic_매매봇['s_네임'])
        p_매매봇.start()

        # 감시 루프 구동
        b_동작중 = True
        dt_에러발생 = pd.Timestamp.now()
        while True:
            # 종료시간 이후라면 프로세스 종료
            if pd.Timestamp.now() > pd.Timestamp(self.s_종료시각):
                ret = p_매매봇.terminate() if p_매매봇.is_alive() else None
                b_동작중 = False

            # 종료시간 내 비정상 종료 시 재시작
            elif not p_매매봇.is_alive():
                # 오류 발생 시 재실행
                if p_매매봇.exitcode == 1:
                    # 연속 재실행 검사
                    if pd.Timestamp.now() - dt_에러발생 < pd.Timedelta(seconds=3):
                        b_동작중 = False
                        continue
                    # 모듈 재실행
                    self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=f'{p_매매봇.name} 모듈 재시작')
                    p_매매봇 = mp.Process(target=dic_매매봇['s_타겟'], name=dic_매매봇['s_네임'])
                    p_매매봇.start()
                    dt_에러발생 = pd.Timestamp.now()

                # 이외 경우에는 오류 알림
                else:
                    self.send_카톡_오류발생(s_프로세스명=p_매매봇.name, n_오류코드=p_매매봇.exitcode)
                    b_동작중 = False

            # 동작 종료 시 감시 루프 해제
            if not b_동작중:
                break

            # 확인 주기 설정
            time.sleep(0.1)

        # 프로세스 종료 처리
        p_매매봇.join()

        # 로그 기록
        if p_매매봇.exitcode <= 0:
            self.make_로그(f'{p_매매봇.name} 구동 완료')
        else:
            self.send_카톡_오류발생(s_프로세스명=p_매매봇.name, n_오류코드=p_매매봇.exitcode)

    def send_카톡_오류발생(self, s_프로세스명, n_오류코드):
        """ 실행 오류 발생 시 프로세스명 포함하여 카톡 메세지 송부 """
        # 메세지 정의
        s_메세지 = (f'!!! [{self.s_파일명}] !!!\n'
                 f'오류 발생 - {s_프로세스명} | code {n_오류코드}')

        # 메세지 송부
        self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=s_메세지)


def run():
    """ 실행 함수 """
    l = LauncherTrader()
    l.run_트레이더()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
