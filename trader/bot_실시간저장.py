import _queue
import os
import sys
import json
import time
import shutil

import pandas as pd
import multiprocessing as mp

import ut, xapi


# ===== 호가잔량 (2026-10-07) =====
# 체결틱과 함께 주식호가잔량(0D)을 받아 csv 로 저장한다 (바로 읽을 수 있게 압축하지 않는다) - 체결보다 먼저 움직이는 정보(매도 잔량 소진 등)가 있는지 보려는 원천 자료
#   10단계 매도·매수 호가와 수량, 총잔량, 예상체결가·수량 (직전대비·LP·KRX/NXT 구분 잔량은 뺀다). 매매에는 쓰지 않는다
#   호가는 체결보다 훨씬 자주 와서 디스크를 많이 쓴다 → 저장 폴더 디스크 여유가 N_호가최소여유 미만이면 호가만 버린다 (체결틱이 우선)
LI_호가컬럼 = (['호가시간'] + [f'매도호가{i}' for i in range(1, 11)] + [f'매도호가수량{i}' for i in range(1, 11)]
             + [f'매수호가{i}' for i in range(1, 11)] + [f'매수호가수량{i}' for i in range(1, 11)]
             + ['매도호가총잔량', '매수호가총잔량', '예상체결가', '예상체결수량'])
N_호가배치 = 2000
N_호가최소여유 = 5e9                 # 바이트


def 호가행(s_종목코드, dic_값, fid=None):
    """ 주식호가잔량 수신값 → csv 한 줄 (없는 항목은 빈칸) - trader/bot_추가수집 도 같이 쓴다 """
    fid = fid if fid is not None else xapi.wsFID_kiwoom.fid_주식호가잔량_0D()
    return ','.join([s_종목코드] + [str(dic_값.get(fid.dic_이름2코드[이름], '')) for 이름 in LI_호가컬럼])


def 호가쓰기(path, li_행, make_로그=None):
    """ csv 에 덧붙인다 (파일이 없으면 머리줄부터) - 디스크 여유가 모자라면 버리고 False """
    try:
        if shutil.disk_usage(os.path.dirname(path)).free < N_호가최소여유:
            return False
        b_새파일 = not os.path.exists(path)
        with open(path, mode='at', encoding='cp949') as f:
            if b_새파일:
                f.write(','.join(['종목코드'] + LI_호가컬럼) + '\n')
            f.write('\n'.join(li_행) + '\n')
        return True
    except Exception as e:
        if make_로그 is not None:
            make_로그(f'호가 파일 쓰기 - {e}')
        return False


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker,PyAttributeOutsideInit
class TraderBot:
    def __init__(self, queue_mp_수신2저장=None):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_trader')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보
        self.folder_주문체결 = dic_폴더정보['매수매도|주문체결']
        self.folder_주식체결 = dic_폴더정보['매수매도|주식체결']
        self.folder_주식호가 = dic_폴더정보['매수매도|주식호가']
        os.makedirs(self.folder_주문체결, exist_ok=True)
        os.makedirs(self.folder_주식체결, exist_ok=True)
        os.makedirs(self.folder_주식호가, exist_ok=True)

        # queue 생성
        self.queue_mp_수신2저장 = queue_mp_수신2저장

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')

        # 로그 기록
        self.make_로그(f'구동 시작')

    def set_기준정보(self):
        """ 실시간 데이터 저장을 위한 기준정보 정의 """
        # 파일 저장 단위 정의
        dic_n배치크기 = dict(
            주문체결=1,
            주식체결=500
        )

        # 파일 저장 위치 지정
        dic_path = dict(
            주문체결=os.path.join(self.folder_주문체결, f'주문체결_{self.s_오늘}.csv'),
            주식체결=os.path.join(self.folder_주식체결, f'주식체결_{self.s_오늘}.csv')
        )

        # 수집할 데이터 항목 지정
        dic_li컬럼명 = dict(
            주문체결=['계좌번호', '주문번호', '종목코드', '주문업무분류', '주문상태', '종목명',
                  '주문수량', '주문가격', '미체결수량', '체결누계금액', '원주문번호', '주문구분', '매매구분', '매도수구분',
                  '주문체결시간', '체결번호', '체결가', '체결량', '현재가', '최우선매도호가', '최우선매수호가',
                  '단위체결가', '단위체결량', '당일매매수수료', '당일매매세금', '거부사유',
                  '화면번호', '거래소구분', '거래소구분명', 'SOR여부'],
            주식체결=['체결시간', '현재가', '등락율', '거래량', '누적거래량', '누적거래대금', '시가', '고가', '저가', '체결강도',
                  '전일거래량대비비율', '고가시간', '저가시간', '매도체결량', '매수체결량', '매수비율',
                  '매도체결건수', '매수체결건수', '장구분', '거래소구분']
        )

        return dic_n배치크기, dic_path, dic_li컬럼명

    def exec_실시간저장(self):
        """ 웹소켓 API에서 수신받은 데이터를 저장 """
        # 기준정보 정의
        dic_n배치크기, dic_path, dic_li컬럼명 = self.set_기준정보()
        dic_li배치데이터 = {key: [] for key in dic_n배치크기}

        # 호가잔량은 따로 모은다 (체결·주문 파일 쓰기와 분리 - 실패해도 체결 저장에 영향 없게)
        path_호가 = os.path.join(self.folder_주식호가, f'주식호가_{self.s_오늘}.csv')
        fid_호가 = xapi.wsFID_kiwoom.fid_주식호가잔량_0D()
        li_호가배치 = list()
        b_호가중단로그 = False

        # 프로그램 시작 시 파일이 없으면 헤더를 미리 기록
        for s_항목명, path_실시간파일 in dic_path.items():
            if not os.path.exists(path_실시간파일):
                s_컬럼명_헤더 = ','.join(['종목코드'] + dic_li컬럼명[s_항목명])
                with open(path_실시간파일, mode='wt', encoding='cp949') as f:
                    f.write(f'{s_컬럼명_헤더}\n')

        # 루프 구동
        b_동작중 = True
        while True:
            # 데이터 수신 - 큐가 빌 때까지 반복하여 전체 데이터 수집
            li_수신데이터 = list()
            try:
                while True:
                    li_수신데이터 = li_수신데이터 + [self.queue_mp_수신2저장.get_nowait()]

            # 큐에 존재하는 모든 데이터 수집 완료 후 처리
            except _queue.Empty:
                time.sleep(0.01)

            # 대량으로 인출한 데이터 묶음을 처리
            for dic_데이터 in li_수신데이터:
                # 종료 신호 확인
                b_동작중 = False if dic_데이터 == ['종료'] else True

                # 호가잔량 - 별도 묶음 (매 N_호가배치 줄 또는 종료 시 쓰기)
                if b_동작중 and dic_데이터.get('name') == '주식호가잔량':
                    try:
                        li_호가배치.append(호가행(dic_데이터['item'], dic_데이터['values'], fid=fid_호가))
                    except Exception as e:
                        self.make_로그(f'호가 변환 - {e}')
                    continue

                # 등록하지 않은 종류는 버린다 (KeyError 로 저장 모듈이 죽지 않게)
                if b_동작중 and dic_데이터.get('name') not in dic_li배치데이터:
                    continue

                # 수신 데이터를 li_배치데이터에 추가
                if b_동작중:
                    # 데이터 정의
                    s_항목명 = dic_데이터['name']
                    s_종목코드 = dic_데이터['item']
                    dic_데이터_변동 = dic_데이터['values']
                    li_배치데이터 = dic_li배치데이터[s_항목명]

                    # 데이터 처리
                    if s_항목명 == '주문체결':
                        fid = xapi.wsFID_kiwoom.fid_주문체결_00()
                        li_데이터 = [dic_데이터_변동[fid.dic_이름2코드[이름]] if 이름 not in ['매도수구분', '거래소구분']
                                  else fid.dic_매도수구분[dic_데이터_변동[fid.dic_이름2코드[이름]]] if 이름 == '매도수구분'
                                  else fid.dic_거래소구분[dic_데이터_변동[fid.dic_이름2코드[이름]]] if 이름 == '거래소구분'
                                  else None
                                  for 이름 in dic_li컬럼명[s_항목명]]

                    elif s_항목명 == '주식체결':
                        fid = xapi.wsFID_kiwoom.fid_주식체결_0B()
                        li_데이터 = [dic_데이터_변동[fid.dic_이름2코드[이름]] if 이름 not in ['장구분']
                                  else fid.dic_장구분[dic_데이터_변동[fid.dic_이름2코드[이름]]] if 이름 == '장구분'
                                  else None
                                  for 이름 in dic_li컬럼명[s_항목명]]

                    else:
                        li_데이터 = list()

                    # 데이터 변환
                    s_데이터_한줄 = ','.join([s_종목코드] + li_데이터)
                    li_배치데이터.append(s_데이터_한줄)

                # 파일에 쓸 배치 크기에 도달하면 쓰기 실행
                for s_항목명, li_배치데이터 in dic_li배치데이터.items():
                    n_배치크기 = dic_n배치크기[s_항목명] if b_동작중 else 1
                    if len(li_배치데이터) >= n_배치크기:
                        s_데이터_블록 = '\n'.join(li_배치데이터) + '\n'
                        try:
                            with open(dic_path[s_항목명], mode='at', encoding='cp949') as f:
                                f.write(s_데이터_블록)
                            dic_li배치데이터[s_항목명].clear()
                        except Exception as e:
                            self.make_로그(f'파일 쓰기 - {e}')

            # 호가 묶음 쓰기 (종료 신호면 남은 것까지)
            if li_호가배치 and (len(li_호가배치) >= N_호가배치 or not b_동작중):
                if not 호가쓰기(path_호가, li_호가배치, make_로그=self.make_로그) and not b_호가중단로그:
                    self.make_로그(f'!!! 호가 저장 건너뜀 (디스크 여유 {N_호가최소여유 / 1e9:.0f}GB 미만 또는 쓰기 실패) - 체결틱 저장은 계속')
                    b_호가중단로그 = True
                li_호가배치 = list()

            # 종료 신호 수신 시 종료
            if not b_동작중:
                break


# noinspection SpellCheckingInspection,PyPep8Naming,NonAsciiCharacters
def run(queue_mp_수신2저장=None):
    queue_mp_수신2저장 = queue_mp_수신2저장 if queue_mp_수신2저장 is not None else mp.Queue()
    t = TraderBot(queue_mp_수신2저장=queue_mp_수신2저장)
    t.exec_실시간저장()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
