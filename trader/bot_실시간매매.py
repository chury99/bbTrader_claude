import os
import re
import sys
import json
import time

import pandas as pd
import multiprocessing as mp
import asyncio

import ut, xapi


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker,PyAttributeOutsideInit,PyUnresolvedReferences
class TraderBot:
    def __init__(self, n_분봉틱, queue_mp_수신2매매=None):
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
        self.folder_감시종목 = dic_폴더정보['매수매도|감시종목']

        # api 정의
        self.wsapi = xapi.WebsocketAPI_kiwoom.WebsocketAPIkiwoom()
        self.restapi = xapi.RestAPI_kiwoom.RestAPIkiwoom()

        # queue 생성
        self.queue_mp_수신2매매 = queue_mp_수신2매매

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.dic_주식체결fid = xapi.wsFID_kiwoom.fid_주식체결_0B().dic_이름2코드
        self.n_tr딜레이 = 0.2
        self.n_분봉틱 = n_분봉틱
        self.dic_분봉 = dict()
        self.dic_체결정보 = dict()

        # 로그 기록
        self.make_로그(f'구동 시작')

    async def exec_종목감시(self):
        """ 큐에서 들어오는 종목 대상으로 매매조건 감시 및 주문 """
        # 루프 구동
        while True:
            # 데이터 수신
            try:
                dic_데이터 = self.queue_mp_수신2매매.get_nowait()
                s_데이터타입 = dic_데이터['name']
                s_종목코드 = dic_데이터['item']
                dic_데이터_변동 = dic_데이터['values']
            except mp.queues.Empty:
                await asyncio.sleep(0.01)
                continue

            # 주식체결 아닐 시 예외처리
            if s_데이터타입 != '주식체결': continue

            # 체결정보 업데이트
            self.dic_체결정보.setdefault(s_종목코드, list()).append(await self._update_체결정보(dic_데이터_변동=dic_데이터_변동))

            # 분봉 업데이트
            df_분봉 = await self._update_분봉정보(s_종목코드=s_종목코드)

    # 지표 업데이트 - 별도 모듈 만들지 말고, 다른 모듈 내부에서 변수만 업데이트
    # 트리거는 큐로 들어오는 데이터 - 해당 종목에 대해서 비동기 구동으로 진행 - 보유 종목이면 judge_매도, 미보유 종목이면 judge_매수
    # 보유종목은 최초구동 + 매수/매도 주문 시 조회


    async def exec_분봉조회(self):
        """ 대상종목의 3분봉 정보를 restapi로 조회 """
        # 감시종목 불러오기 (수신 모듈이 파일 생성 전이면 대기 - 기동 순서 레이스 방지)
        li_파일 = list()
        for _ in range(60):
            li_파일 = [파일 for 파일 in os.listdir(self.folder_감시종목)
                     if '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] <= self.s_오늘]
            if len(li_파일) > 0:
                break
            await asyncio.sleep(1)
        if len(li_파일) == 0:
            self.make_로그('감시종목 파일 미존재 - 분봉조회 중단')
            return
        s_파일명 = max(li_파일)
        dic_감시종목 = pd.read_pickle(os.path.join(self.folder_감시종목, s_파일명))
        li_감시종목 = dic_감시종목.get('매매대상', list())

        # 분봉 조회
        dic_분봉 = dict()
        for s_종목코드 in li_감시종목:
            # tr 조회
            df_분봉 = self.restapi.tr_주식분봉차트조회요청(s_종목코드=s_종목코드, s_틱범위=str(self.n_분봉틱))
            await asyncio.sleep(self.n_tr딜레이)

            # 분봉 업데이트
            df_분봉.index = pd.to_datetime(df_분봉['일자'] + ' ' + df_분봉['시간'])
            df_분봉['atr'] = pd.concat([df_분봉['고가'] - df_분봉['저가'],
                                       (df_분봉['고가'] - df_분봉['종가'].shift(1)).abs(),
                                       (df_분봉['저가'] - df_분봉['종가'].shift(1)).abs()], axis=1).max(axis=1)
            df_분봉['atr'] = df_분봉['atr'].ewm(span=14, adjust=False).mean()
            df_분봉 = df_분봉.sort_index()

            # 미완성 봉 제외
            if pd.Timestamp.now() - df_분봉.index[-1] < pd.Timedelta(minutes=self.n_분봉틱):
                df_분봉 = df_분봉.iloc[:-1]

            # 데이터 추가
            self.dic_분봉[s_종목코드] = df_분봉
            print(f'분봉수집-{s_종목코드}')

    async def _update_체결정보(self, dic_데이터_변동):
        """ 수신한 체결정보를 종목별로 정리하여 리턴 """
        # 체결정보 정리
        dic_체결정보_종목 = dict(
            체결시간=dic_데이터_변동[self.dic_주식체결fid['체결시간']],
            현재가=abs(int(dic_데이터_변동[self.dic_주식체결fid['현재가']])),
            등락율=float(dic_데이터_변동[self.dic_주식체결fid['등락율']]),
            누적거래량=int(dic_데이터_변동[self.dic_주식체결fid['누적거래량']]),
            누적거래대금=int(dic_데이터_변동[self.dic_주식체결fid['누적거래대금']]),
            시가=abs(int(dic_데이터_변동[self.dic_주식체결fid['시가']])),
            고가=abs(int(dic_데이터_변동[self.dic_주식체결fid['고가']])),
            저가=abs(int(dic_데이터_변동[self.dic_주식체결fid['저가']])),
            체결강도=float(dic_데이터_변동[self.dic_주식체결fid['체결강도']]),
            고가시간=dic_데이터_변동[self.dic_주식체결fid['고가시간']],
            저가시간=dic_데이터_변동[self.dic_주식체결fid['저가시간']]
        )

        # 포맷 정리
        s_체결시간 = dic_체결정보_종목['체결시간']
        dic_체결정보_종목.update(체결시간=f'{s_체결시간[:2]}:{s_체결시간[2:4]}:{s_체결시간[4:]}')

        return dic_체결정보_종목

    async def _update_분봉정보(self, s_종목코드):
        """ 체결정보 가공하여 기존 분봉정보 업데이트 후 리터 """
        # 기존 분봉정보 불러오기
        # while (df_기존분봉 := self.dic_분봉.get(s_종목코드)) is None:
        #     await asyncio.sleep(self.n_tr딜레이)
        if s_종목코드 not in self.dic_분봉.keys(): return pd.DataFrame()

        # 최종시간 확인

        # 체결정보 가공

        # 분봉정보 추가


        # return df_분봉
        return None












    async def exec_감시종목등록(self):
        """ 감시종목 폴더에 저장된 종목을 웹소켓 서버에 등록 """
        # 감시종목 생성 - 임시
        folder = '/Users/ProjectWork/bbTrader/분석/백테스팅/돌파매매/10_종목선정'
        s_일자 = max(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder) if '.pkl' in 파일)
        df_종목선정 = pd.read_pickle(os.path.join(folder, f'df_종목선정_{s_일자}.pkl'))
        df_종목선정 = df_종목선정[df_종목선정['종목선정']]
        li_감시종목 = df_종목선정['종목코드'].to_list()
        pd.to_pickle(li_감시종목, os.path.join(self.folder_감시종목, f'li_감시종목_{s_일자}.pkl'))

        # 감시종목 불러오기
        s_파일명 = max(파일 for 파일 in os.listdir(self.folder_감시종목)
                    if '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] <= self.s_오늘)
        li_감시종목 = pd.read_pickle(os.path.join(self.folder_감시종목, s_파일명))

        # 감시종목 등록
        res = await self.wsapi.req_실시간등록(li_종목코드=li_감시종목, li_데이터타입=['주문체결', '주식체결'])

        # 로그 기록
        self.make_로그(f'총 {len(li_감시종목)}개\n'
                     f'{res}')

    async def exec_콘솔(self):
        """ 웹소켓 API에서 수신받은 데이터를 콘솔에 출력 """
        # 루프 구동
        while True:
            # 데이터 수신
            li_데이터 = await self.wsapi.queue_콘솔.get()

            # 데이터 순차 처리
            for dic_데이터 in li_데이터:
                s_데이터타입 = dic_데이터['name']
                s_종목코드 = dic_데이터['item']
                dic_데이터_변동 = dic_데이터['values']

                # 데이터 출력
                print(f'{len(li_데이터)}개 수신 - {s_데이터타입} - {s_종목코드}|{dic_데이터_변동}')

    async def exec_저장(self):
        """ 웹소켓 API에서 수신받은 데이터를 저장 모듈로 전달 """
        # 루프 구동
        while True:
            # 데이터 수신
            li_데이터 = await self.wsapi.queue_저장.get()
            if self.queue_mp_수신2저장 is None: continue

            # 데이터 순차 처리
            for dic_데이터 in li_데이터:
                s_데이터타입 = dic_데이터['name']
                s_종목코드 = dic_데이터['item']
                dic_데이터_변동 = dic_데이터['values']

                # 데이터 전달
                self.queue_mp_수신2저장.put(dic_데이터)

            # # 데이터 전달
            # if self.queue_mp_수신2저장 is not None:
            #     self.queue_mp_수신2저장.put(dic_데이터)

    async def exec_매매(self):
        """ 웹소켓 API에서 수신받은 데이터를 매매 모듈로 전달 """
        # 루프 구동
        while True:
            # 데이터 수신
            li_데이터 = await self.wsapi.queue_매매.get()
            if self.queue_mp_수신2저장 is None: continue

            # 데이터 순차 처리
            for dic_데이터 in li_데이터:
                s_데이터타입 = dic_데이터['name']
                s_종목코드 = dic_데이터['item']
                dic_데이터_변동 = dic_데이터['values']

                # 데이터 전달
                self.queue_mp_수신2매매.put(dic_데이터)

    async def run_실시간매매(self):
        """ exec 함수들을 비동기로 구동 """
        # task 활성화
        await asyncio.gather(
            self.exec_종목감시(),
            self.exec_분봉조회()
        )


# noinspection SpellCheckingInspection,PyPep8Naming,NonAsciiCharacters
def run(queue_mp_수신2매매=None):
    queue_mp_수신2매매 = queue_mp_수신2매매 if queue_mp_수신2매매 is not None else mp.Queue()
    t = TraderBot(n_분봉틱=3, queue_mp_수신2매매=queue_mp_수신2매매)
    asyncio.run(t.run_실시간매매())


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
