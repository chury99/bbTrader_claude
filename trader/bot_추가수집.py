import os
import re
import sys
import time

import pandas as pd
import asyncio

import ut, xapi, trader

# ===== 추가 감시종목 틱 수집 (2026-10-01) =====
# 키움 실시간 등록은 계좌당 100종목이라, 두 번째 계좌(config '계좌번호_추가수집')로 100종목을 더 받는다.
#   본 감시종목 100 은 1분 +4% 급등의 12% 만 담는다 (분봉 1년 연구) → 장 시작 전 급등 점수(ut.분봉급등.점수표) 상위 100 을
#   본 감시종목과 겹치지 않게 골라 틱만 모은다. 매매에는 쓰지 않는다 (관성매매 1초 캐시가 본 틱과 합쳐 읽는다).
# 실패해도 본 수신·저장·매매에 영향이 없도록 실행기가 감시 루프 밖에서 따로 돌리고, 여기서도 예외는 로그만 남기고 끝낸다.
N_추가종목 = 100
N_감시대기초 = 300              # 오늘 본 감시종목 파일을 기다리는 최대 시간 (bot_실시간수신 이 시작하자마자 만든다)
N_최소가격 = 1000
N_배치, N_쓰기주기초 = 500, 1.0
N_종료여유초 = 30               # 실행기가 종료시각에 끄기 전에 스스로 마지막 묶음을 쓰고 끝낸다
# 저장 컬럼은 trader/bot_실시간저장.py 의 주식체결 컬럼과 같다 (관성매매 1초 캐시가 두 파일을 같은 방식으로 읽는다)
LI_컬럼 = ['체결시간', '현재가', '등락율', '거래량', '누적거래량', '누적거래대금', '시가', '고가', '저가', '체결강도',
          '전일거래량대비비율', '고가시간', '저가시간', '매도체결량', '매수체결량', '매수비율',
          '매도체결건수', '매수체결건수', '장구분', '거래소구분']


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker,PyAttributeOutsideInit
class TraderBot:
    def __init__(self):
        # config 읽어 오기
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_trader')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보
        self.folder_감시종목 = dic_폴더정보['매수매도|감시종목']
        self.folder_추가감시 = dic_폴더정보['매수매도|감시종목추가']
        self.folder_추가틱 = dic_폴더정보['매수매도|주식체결추가']
        self.folder_호가 = dic_폴더정보['매수매도|주식호가']
        self.folder_대상종목 = dic_폴더정보['데이터|대상종목']
        os.makedirs(self.folder_추가감시, exist_ok=True)
        os.makedirs(self.folder_추가틱, exist_ok=True)
        os.makedirs(self.folder_호가, exist_ok=True)

        # 기준정보 정의
        self.s_계좌번호 = str(dic_config.get('계좌번호_추가수집', '') or '')
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.dt_종료 = pd.Timestamp(dic_config['종료시각']) - pd.Timedelta(seconds=N_종료여유초)
        self.path_틱 = os.path.join(self.folder_추가틱, f'주식체결추가_{self.s_오늘}.csv')
        self.path_호가 = os.path.join(self.folder_호가, f'주식호가추가_{self.s_오늘}.csv.gz')     # 2026-10-07 호가잔량도 함께
        self.li_추가종목 = list()

        # 로그 기록
        self.make_로그('구동 시작')

    def _read_감시종목(self):
        """ 오늘 본 감시종목 100 - 파일이 생길 때까지 기다리고, 끝내 없으면 가장 최근 파일 (경고) """
        dt_한도 = pd.Timestamp.now() + pd.Timedelta(seconds=N_감시대기초)
        path_오늘 = os.path.join(self.folder_감시종목, f'dic_감시종목_{self.s_오늘}.pkl')
        while not os.path.exists(path_오늘) and pd.Timestamp.now() < dt_한도:
            time.sleep(2)
        if os.path.exists(path_오늘):
            time.sleep(1)                                         # 쓰는 중인 파일을 읽지 않게
            path = path_오늘
        else:
            li = sorted(f for f in os.listdir(self.folder_감시종목) if f.startswith('dic_감시종목_') and f.endswith('.pkl'))
            if not li:
                return list()
            path = os.path.join(self.folder_감시종목, li[-1])
            self.make_로그(f'!!! 오늘 감시종목 파일 없음 - {li[-1]} 로 겹침 제외')
        dic = pd.read_pickle(path)
        return dic.get('조회순위포함', list()) + dic.get('조회순위미포함', list())

    def make_추가감시종목(self):
        """ 급등 점수 상위 100 (본 감시종목·가격 1,000원 미만·분석대상 밖 종목 제외) → 저장 """
        df = ut.분봉급등.점수표(self.s_오늘)
        if len(df) == 0:
            self.make_로그('!!! 분봉 자료 부족 - 추가 감시종목 없음')
            return
        li_감시 = set(self._read_감시종목())
        df = df[(df['전일종가'] >= N_최소가격) & ~df.index.isin(li_감시)]

        # 분석대상종목(관리종목·우선주 등을 걷어낸 모집단) 이 있으면 그 안에서만 - 본 감시종목과 같은 기준
        li_대상 = sorted(f for f in os.listdir(self.folder_대상종목) if f.startswith('df_대상종목') and f.endswith('.pkl')
                       and re.findall(r'\d{8}', f)[0] < self.s_오늘) if os.path.exists(self.folder_대상종목) else []
        if li_대상:
            li_거래대상 = set(pd.read_pickle(os.path.join(self.folder_대상종목, li_대상[-1]))['종목코드'])
            df = df[df.index.isin(li_거래대상)]

        df = df.head(N_추가종목)
        self.li_추가종목 = df.index.to_list()
        pd.to_pickle(dict(추가감시=self.li_추가종목, 점수표=df), os.path.join(self.folder_추가감시, f'dic_추가감시종목_{self.s_오늘}.pkl'))
        self.make_로그(f'총 {len(self.li_추가종목)}개 (본 감시 {len(li_감시)}개 제외, 점수 {df["점수"].min():.2f} ~ {df["점수"].max():.2f})')

    async def exec_저장(self, wsapi):
        """ 주식체결은 csv, 주식호가잔량은 gzip csv 로 묶어 쓴다 (주문체결은 이 계좌로 주문을 내지 않으므로 버린다) """
        fid = xapi.wsFID_kiwoom.fid_주식체결_0B()
        fid_호가 = xapi.wsFID_kiwoom.fid_주식호가잔량_0D()
        li_호가 = list(); b_호가중단로그 = False
        if not os.path.exists(self.path_틱):
            with open(self.path_틱, mode='wt', encoding='cp949') as f:
                f.write(','.join(['종목코드'] + LI_컬럼) + '\n')
        li_배치 = list()
        t_쓰기 = time.time()
        while pd.Timestamp.now() < self.dt_종료:
            try:
                li_데이터 = await asyncio.wait_for(wsapi.queue_저장.get(), timeout=N_쓰기주기초)
            except asyncio.TimeoutError:
                li_데이터 = list()
            for dic in li_데이터 or list():
                if dic.get('name') == '주식호가잔량':
                    li_호가.append(trader.bot_실시간저장.호가행(dic['item'], dic['values'], fid=fid_호가))
                    continue
                if dic.get('name') != '주식체결':
                    continue
                v = dic['values']
                li_배치.append(','.join([dic['item']] + [fid.dic_장구분[v[fid.dic_이름2코드[이름]]] if 이름 == '장구분' else v[fid.dic_이름2코드[이름]]
                                                         for 이름 in LI_컬럼]))
            if li_배치 and (len(li_배치) >= N_배치 or time.time() - t_쓰기 >= N_쓰기주기초):
                self._쓰기(li_배치)
                li_배치 = list(); t_쓰기 = time.time()
            if len(li_호가) >= trader.bot_실시간저장.N_호가배치:
                if not trader.bot_실시간저장.호가쓰기(self.path_호가, li_호가, make_로그=self.make_로그) and not b_호가중단로그:
                    self.make_로그('!!! 호가 저장 건너뜀 (디스크 여유 부족 또는 쓰기 실패) - 체결틱 저장은 계속'); b_호가중단로그 = True
                li_호가 = list()
        if li_배치:
            self._쓰기(li_배치)
        if li_호가:
            trader.bot_실시간저장.호가쓰기(self.path_호가, li_호가, make_로그=self.make_로그)
        wsapi.b_동작중 = False

    def _쓰기(self, li_배치):
        try:
            with open(self.path_틱, mode='at', encoding='cp949') as f:
                f.write('\n'.join(li_배치) + '\n')
        except Exception as e:
            self.make_로그(f'파일 쓰기 - {e}')

    @staticmethod
    async def exec_비우기(queue):
        """ 쓰지 않는 큐(콘솔·매매)를 비운다 - 그냥 두면 장중 내내 쌓인다 """
        while True:
            await queue.get()

    async def run_수신(self):
        """ 두 번째 계좌로 웹소켓 접속 → 추가 감시종목 주식체결 등록 → 종료시각까지 저장 """
        wsapi = xapi.WebsocketAPI_kiwoom.WebsocketAPIkiwoom(s_계좌번호=self.s_계좌번호)
        wsapi.b_자동재접속 = True
        await wsapi.ws_서버접속()
        task_수신 = asyncio.create_task(wsapi.ws_수신관리())
        li_비우기 = [asyncio.create_task(self.exec_비우기(q)) for q in (wsapi.queue_콘솔, wsapi.queue_매매)]
        await asyncio.sleep(1)
        res = await wsapi.req_실시간등록(li_종목코드=self.li_추가종목, li_데이터타입=['주식체결', '주식호가잔량'])
        self.make_로그(f'등록 {len(self.li_추가종목)}개 - {str(res)[:80]}')
        await self.exec_저장(wsapi)
        for t in li_비우기 + [task_수신]:
            t.cancel()
        try:
            await wsapi.ws_접속해제()
        except Exception:
            pass


# noinspection SpellCheckingInspection,PyPep8Naming,NonAsciiCharacters
def run():
    t = TraderBot()
    if not t.s_계좌번호:
        t.make_로그('계좌번호_추가수집 설정 없음 - 추가 수집 안 함')
        return
    try:
        t.make_추가감시종목()
        if t.li_추가종목 and pd.Timestamp.now() < t.dt_종료:
            asyncio.run(t.run_수신())
    except Exception as e:
        t.make_로그(f'!!! 추가 수집 중단 - {type(e).__name__}: {e}')
    t.make_로그('구동 완료')


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
