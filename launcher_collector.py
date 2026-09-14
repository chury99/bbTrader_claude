import os
import sys
import time

import pandas as pd
import multiprocessing as mp

import collector, ut


# 차트수집 시작시각 - 시간외 단일가(16:00~18:00)가 끝난 뒤라 당일 일봉이 확정값이고, 분석 실행기(15:40)와 키움 조회가 겹치지 않는다
S_차트수집시각 = '18:10:00'


# noinspection NonAsciiCharacters,PyPep8Naming,SpellCheckingInspection,PyUnreachableCode
class LauncherCollector:
    """ 데이터 수집 실행기 (08:50 기동) - spTraderV2 launcher_collector 를 대신한다

        · 기동 즉시  조회순위   종료시각까지 30초마다 (별도 프로세스, 다른 단계가 막혀도 계속 돈다)
        · 기동 즉시  정보수집   전체종목 · 조건검색 · 대상종목 (10분 넘게 안 끝나면 끊고 알림)
        · 18:10      차트수집   전체종목 일봉·분봉 db → 캐시생성 일봉 캐시
        늦게 띄우면 지난 단계는 곧바로 실행한다 (조회순위는 종료시각이 지났으면 바로 끝남) """

    # noinspection PyUnresolvedReferences
    def __init__(self):
        # config 읽어 오기
        self.folder_프로젝트 = os.path.dirname(os.path.abspath(__file__))
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_collector')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def run_모듈(self, obj_타겟, s_네임, b_재실행=False, n_제한초=None):
        """ 모듈을 별도 프로세스로 실행하고 끝날 때까지 대기
            b_재실행 이면 비정상 종료 시 다시 띄운다 (이어받기 되는 모듈용), n_제한초 를 넘기면 강제 종료한다 """
        # 프로세스 실행 - 비정상 종료 시 재실행
        dt_에러발생 = pd.Timestamp.now()
        while True:
            # 프로세스 구동
            p_봇 = mp.Process(target=obj_타겟, name=s_네임)
            p_봇.start()
            p_봇.join(timeout=n_제한초)

            # 제한시간 초과 시 강제 종료
            if p_봇.is_alive():
                p_봇.terminate()
                p_봇.join()
                self.make_로그(f'!!! {p_봇.name} {n_제한초}초 초과 - 강제 종료')
                self.send_카톡_오류발생(s_프로세스명=p_봇.name, n_오류코드=f'{n_제한초}초 초과 강제 종료')
                return

            # 정상 종료 또는 재실행 대상 아니면 종료
            if p_봇.exitcode <= 0 or not b_재실행:
                break

            # 비정상 종료 처리 - 3초 안에 연달아 죽으면 중단
            time.sleep(1)
            if pd.Timestamp.now() - dt_에러발생 < pd.Timedelta(seconds=3):
                break
            self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=f'{p_봇.name} 모듈 재시작')
            dt_에러발생 = pd.Timestamp.now()

        # 로그 기록
        if p_봇.exitcode <= 0:
            self.make_로그(f'{p_봇.name} 구동 완료')
        else:
            self.send_카톡_오류발생(s_프로세스명=p_봇.name, n_오류코드=p_봇.exitcode)

    def run_정보수집(self):
        """ 전체종목·조건검색·대상종목 수집 """
        self.run_모듈(obj_타겟=collector.bot_정보수집.run, s_네임='bot_정보수집', n_제한초=600)

    def start_조회순위(self):
        """ 조회순위 수집을 별도 프로세스로 띄우고 바로 돌아온다 (종료시각에 스스로 끝남) """
        p_봇 = mp.Process(target=collector.bot_조회순위.run, name='bot_조회순위')
        p_봇.start()
        self.make_로그(f'{p_봇.name} 구동')
        return p_봇

    def run_차트수집(self):
        """ 전체종목 일봉·분봉 수집 - 받은 데까지 저장돼 있어 비정상 종료 시 다시 띄워 이어받는다 """
        self.run_모듈(obj_타겟=collector.bot_차트수집.run, s_네임='bot_차트수집', b_재실행=True)

    def run_캐시생성(self):
        """ 일봉 캐시 생성 - 차트수집 뒤에 진행 """
        self.run_모듈(obj_타겟=collector.bot_캐시생성.run, s_네임='bot_캐시생성')

    def send_카톡_오류발생(self, s_프로세스명, n_오류코드):
        """ 실행 오류 발생 시 프로세스명 포함하여 카톡 메세지 송부 """
        # 메세지 정의
        s_메세지 = (f'!!! [{self.s_파일명}] !!!\n'
                 f'오류 발생 - {s_프로세스명} | code {n_오류코드}')

        # 메세지 송부
        self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=s_메세지)


def run():
    """ 실행 함수 """
    l = LauncherCollector()

    # 기동 즉시 - 조회순위 수집을 먼저 띄우고 정보수집 (조건검색이 막혀도 조회순위는 쌓이게)
    p_조회순위 = l.start_조회순위()
    l.run_정보수집()

    # 차트수집 시각까지 대기
    dt_차트수집 = pd.Timestamp(S_차트수집시각)
    while pd.Timestamp.now() < dt_차트수집:
        print(f'\r[{pd.Timestamp.now():%H:%M:%S}] 차트수집({S_차트수집시각}) - {str(dt_차트수집 - pd.Timestamp.now()).split(" ")[-1].split(".")[0]} 후 실행',
              end='', flush=True)
        time.sleep(1)
    print()

    # 조회순위 종료 확인
    p_조회순위.join()
    if p_조회순위.exitcode > 0:
        l.send_카톡_오류발생(s_프로세스명=p_조회순위.name, n_오류코드=p_조회순위.exitcode)

    # 장 마감 후 - 차트수집 → 캐시생성
    l.run_차트수집()
    l.run_캐시생성()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
