import os
import sys
import json
import time

import pandas as pd
import asyncio
import websockets

import ut, xapi


# noinspection SpellCheckingInspection,NonAsciiCharacters,PyPep8Naming,PyAttributeOutsideInit
class WebsocketAPIkiwoom:
    def __init__(self):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 기준정보 정의
        self.s_서버구분 = dic_config['서버구분']    # 실서버, 모의서버
        self.s_거래소 = dic_config['거래소구분']    # KRX:한국거래소, NXT:넥스트트레이드
        self.s_서버주소 = self.info_서버주소()

        # 변수 정의
        self.websocket = None
        self.b_연결상태 = False
        self.b_동작중 = True

        # 자동 재접속 정의
        self.b_자동재접속 = False       # 연결 끊김 시 자동 재접속 여부 (실시간 수신에서 True 설정)
        self.n_재접속대기 = 5           # 재접속 시도 간격 (초)
        self.li_구독목록 = list()       # 재접속 시 재등록할 구독 정보
        self.event_로그인 = asyncio.Event()    # LOGIN 응답 수신 완료 이벤트 (등록 요청은 로그인 완료 후 송신)
        self.n_로그인실패 = 0           # 연속 로그인 실패 횟수 (3회 이상 시 동작 종료)

        # queue 정의
        self.queue_매매 = asyncio.Queue()
        self.queue_콘솔 = asyncio.Queue()
        self.queue_저장 = asyncio.Queue()
        self.queue_조건검색 = asyncio.Queue()

        # 토큰 발급
        self.s_접근토큰 = xapi.RestAPI_kiwoom.RestAPIkiwoom().s_접근토큰

    def info_서버주소(self, s_서비스='공통'):
        """ 서비스명을 입력받아 해당하는 서버 주소 리턴 """
        # 기준정보 정의 - 호스트명
        dic_호스트 = dict(
            실서버='wss://api.kiwoom.com:10000',
            모의서버='wss://mockapi.kiwoom.com:10000'
        )

        # 기준정보 정의 - 서비스명
        dic_서비스 = dict(
            실시간시세='/api/dostk/websocket',
            조건검색='/api/dostk/websocket',
            공통='/api/dostk/websocket')

        # 서버주소 생성
        url_호스트 = dic_호스트[self.s_서버구분]
        url_서비스 = dic_서비스[s_서비스] if s_서비스 in dic_서비스 else None
        s_서버주소 = f'{url_호스트}{url_서비스}' if url_서비스 is not None else 'err_서비스미존재'

        return s_서버주소

    async def ws_서버접속(self):
        """ 서버에 연결 요청 """
        try:
            # 웹소켓 연결
            self.event_로그인.clear()
            self.websocket = await websockets.connect(self.s_서버주소)
            self.b_연결상태 = True

            # 로그인 요청
            dic_바디 = dict(trnm='LOGIN', token=self.s_접근토큰)
            await self.ws_메세지송부(dic_바디=dic_바디)

        except Exception as e:
            print(f'서버접속 실패 - {e}', file=sys.stderr)
            self.b_연결상태 = False

    async def ws_접속해제(self):
        """ 서버 접속 종료 """
        # 동작중 flag 초기화
        self.b_동작중 = False

        # 접속 종료
        if self.b_연결상태 and self.websocket:
            await self.websocket.close()
            self.b_연결상태 = False
            print('서버접속 해제')

    async def ws_메세지송부(self, dic_바디):
        """ 서버로 요청 메세지 송부 (연결 없으면 자동으로 연결) """
        # 연결 없을 시 연결
        if not self.b_연결상태:
            await self.ws_서버접속()

        # 연결 실패 시 전송 중단 (None.send() 방지)
        if not self.b_연결상태 or self.websocket is None:
            print('메세지 송부 실패 - 서버 미연결', file=sys.stderr)
            return

        # 요청 메세지 전송
        dic_바디 = json.dumps(dic_바디) if not isinstance(dic_바디, str) else dic_바디
        await self.websocket.send(dic_바디)

    async def ws_메세지수신(self):
        """ 서버에서 오는 메세지 수신 """
        # 수신 대기 (동작중 일때만 대기)
        while self.b_동작중:
            try:
                # 수신 데이터 변환
                res = json.loads(await self.websocket.recv())
                s_서비스 = res.get('trnm')
                s_리턴코드 = res.get('return_code')
                s_리턴메세지 = res.get('return_msg')
                if s_리턴코드 != 0 and s_리턴코드 is not None:
                    print(f'수신 이상 - {s_서비스}|{s_리턴메세지}')

                # 결과 처리 - PING (수신값 그대로 재송신)
                if s_서비스 == 'PING':
                    await self.ws_메세지송부(res)

                # 결과 처리 - LOGIN (성공 시 이벤트 set - 등록 요청 허용, 실패 시 재시도/종료)
                elif s_서비스 == 'LOGIN':
                    if s_리턴코드 != 0:
                        self.n_로그인실패 += 1
                        print(f'로그인 실패({self.n_로그인실패}회) - {res.get('return_msg')}', file=sys.stderr)
                        if self.b_자동재접속 and self.n_로그인실패 < 3:
                            await self.websocket.close()    # 연결만 종료 - 수신관리가 재접속
                        else:
                            await self.ws_접속해제()          # 반복 실패 - 동작 종료
                    else:
                        self.n_로그인실패 = 0
                        self.event_로그인.set()

                # 결과 처리 - REG, REMOVE (등록/해지: 실패해도 연결은 유지 - 전체 중단 방지)
                elif s_서비스 in ['REG', 'REMOVE']:
                    if s_리턴코드 != 0:
                        print(f'종목등록/해지 실패 - {s_서비스} - {res.get('return_msg')}', file=sys.stderr)
                        if not self.b_자동재접속:
                            await self.ws_접속해제()

                # 결과 처리 - REAL (실시간시세 - 데이터 처리 함수 호출)
                elif s_서비스 == 'REAL':
                    await self.proc_실시간시세(res)

                # 결과 처리 - CNSR (조건검색 - 데이터 처리 함수 호출)
                elif s_서비스[:4] == 'CNSR':
                    await self.queue_조건검색.put(res)
                    if s_서비스 == 'CNSRREQ' and 'cont_yn' not in res:
                        self.b_동작중 = False
                    elif res.get('cont_yn') == 'N':
                        self.b_동작중 = False

                # 결과 처리 - SYSTEM (오류확인용)
                elif s_서비스 == 'SYSTEM':
                    pass

                # 기타 - 오류 메세지 기록 (자동재접속 모드는 수신 유지, 그 외 중단)
                else:
                    print(f'미등록 서비스 - {s_서비스}', file=sys.stderr)
                    if not self.b_자동재접속:
                        await self.ws_접속해제()

            except websockets.ConnectionClosed:
                # print('서버에 의한 종료')
                self.b_연결상태 = False
                # 자동재접속 모드가 아니면 동작 종료 (자동재접속 모드는 ws_수신관리가 재접속 처리)
                if not self.b_자동재접속:
                    self.b_동작중 = False
                return

            except Exception as e:
                # 개별 메세지 처리 오류 시 루프 유지 (전체 수신 중단 방지)
                print(f'메세지수신 처리 오류 - {e}', file=sys.stderr)
                continue

    async def proc_실시간시세(self, res):
        """ REAL | 실시간시세 데이터 처리 """
        # 수신 데이터 변환
        s_서비스 = res.get('trnm')
        li_데이터 = res.get('data')

        # queue로 데이터 전달
        await self.queue_콘솔.put(li_데이터)
        await self.queue_저장.put(li_데이터)
        await self.queue_매매.put(li_데이터)

    async def req_실시간등록(self, li_종목코드, li_데이터타입, b_기존유지=True, b_등록해지=False):
        """ 실시간시세 조회를 위한 종목코드 및 데이터타입 등록 요청 (주문체결은 미등록시에도 자동 수신) """
        # 기준정보 정의
        dic_데이터타입 = dict(주문체결='00', 잔고='04', 주식기세='0A', 주식체결='0B', 주식우선호가='0C', 주식호가잔량='0D',
                         주식시간외호가='0E', 주식당일거래원='0F', ETFNAV='0G', 주식예상체결='0H', 업종지수='0J', 업종등락='0U',
                         주식종목정보='0g', ELW이론가='0m', 장시작시간='0s', ELW지표='0u', 종목프로그램매매='0w', VI발동해제='1h')

        # 변수 재정의
        li_데이터타입_코드 = [dic_데이터타입[타입] for 타입 in li_데이터타입]
        s_기존유지 = '1' if b_기존유지 else '0'

        # 로그인 완료 대기 (로그인 전 등록 요청 시 서버 거부 - 재접속 직후 순서 보장)
        try:
            await asyncio.wait_for(self.event_로그인.wait(), timeout=10)
        except asyncio.TimeoutError:
            print('실시간등록 실패 - 로그인 응답 타임아웃', file=sys.stderr)
            return 'err_로그인타임아웃'

        # 등록 요청
        li_데이터 = [dict(item=li_종목코드, type=li_데이터타입_코드)]
        dic_바디 = dict(trnm='REG', grp_no='1', refresh=s_기존유지, data=li_데이터)
        if b_등록해지:
            dic_바디 = dict(trnm='REMOVE', grp_no='1', refresh=s_기존유지, data=li_데이터)
        await self.ws_메세지송부(dic_바디=dic_바디)

        # 재접속 재등록용 구독정보 관리
        if not b_등록해지:
            self.li_구독목록.append(dict(li_종목코드=li_종목코드, li_데이터타입=li_데이터타입))

        # 리턴 메세지 생성
        s_리턴메세지 = f'요청 - {li_데이터}'

        return s_리턴메세지

    async def ws_수신관리(self):
        """ 수신 대기 관리 - 연결 끊김 시 자동 재접속 및 구독 재등록 (실시간 수신용) """
        while self.b_동작중:
            # 미연결 시 재접속 및 구독 재등록
            if not self.b_연결상태:
                await self.ws_서버접속()
                if not self.b_연결상태:
                    print(f'재접속 실패 - {self.n_재접속대기}초 후 재시도', file=sys.stderr)
                    await asyncio.sleep(self.n_재접속대기)
                    continue
                # 재등록은 별도 태스크로 실행 - 수신 루프가 LOGIN 응답을 처리해야 등록이 가능하므로 병행 필수
                asyncio.create_task(self.re_구독등록())

            # 수신 대기 (연결 종료 시 리턴)
            await self.ws_메세지수신()

            # 예기치 않은 종료 시 재접속 대기 (정상 종료면 while 조건에서 탈출)
            if self.b_동작중:
                print(f'웹소켓 연결 종료 감지 - {self.n_재접속대기}초 후 재접속', file=sys.stderr)
                await asyncio.sleep(self.n_재접속대기)

    async def re_구독등록(self):
        """ 재접속 시 기존 구독 정보로 실시간 등록 재요청 """
        # 기존 구독목록 스냅샷 후 초기화 (재등록 과정에서 중복 누적 방지)
        li_구독_기존 = list(self.li_구독목록)
        self.li_구독목록 = list()

        # 구독 재등록
        for dic_구독 in li_구독_기존:
            await self.req_실시간등록(li_종목코드=dic_구독['li_종목코드'], li_데이터타입=dic_구독['li_데이터타입'])
        if len(li_구독_기존) > 0:
            print(f'구독 재등록 완료 - {len(li_구독_기존)}건', file=sys.stderr)


# noinspection SpellCheckingInspection,NonAsciiCharacters,PyPep8Naming,PyAttributeOutsideInit
class SimpleWebsocketAPI:
    def __init__(self):
        # API 불러오기
        self.api = WebsocketAPIkiwoom()

    async def req_조건검색(self, s_데이터타입, s_검색식번호='0', s_연속조회여부='N', s_연속조회키=''):
        """ 조건검색 조회 요청 """
        # 바디 정의 - 목록조회
        if s_데이터타입 == '목록조회':
            dic_바디 = dict(trnm='CNSRLST')

        # 바디 정의 - 요청일반
        elif s_데이터타입 == '요청일반':
            dic_바디 = dict(trnm='CNSRREQ',
                          seq=s_검색식번호, search_type='0', stex_tp='K', cont_yn=s_연속조회여부, next_key=s_연속조회키)

        # 바디 정의 - 요청실시간
        elif s_데이터타입 == '요청실시간':
            dic_바디 = dict(trnm='CNSRREQ', seq=s_검색식번호, search_type='1', stex_tp='K')

        # 바디 정의 - 실시간해제
        elif s_데이터타입 == '실시간해제':
            dic_바디 = dict(trnm='CNSRCLR', seq=s_검색식번호)

        # 기타 - 오류 메세지 후 중단
        else:
            dic_바디 = None
            print(f'미등록 데이터타입 - {s_데이터타입}')
            await self.api.ws_접속해제()

        # 서버 요청
        await self.api.ws_메세지송부(dic_바디=dic_바디)

    async def proc_조건검색(self):
        """ api.queue를 통해 전달받은 조건검색 데이터 처리 """
        # 변수 정의
        self.li_목록조회 = list()
        self.li_요청실시간 = list()
        self.li_요청일반 = list()

        # 루프 생성
        while True:
            # 큐 데이터 수신
            res = await self.api.queue_조건검색.get()

            # 수신 데이터 변환
            s_서비스 = res.get('trnm')
            li_데이터 = res.get('data')

            # 서비스별 데이터 처리 - 목록조회
            if s_서비스 == 'CNSRLST':
                self.li_목록조회 = self.li_목록조회 + li_데이터

            # 서비스별 데이터 처리 - 목록조회 - 실시간
            if s_서비스 == 'CNSRREQ' and 'cont_yn' not in res:
                self.li_요청실시간 = self.li_요청실시간 + li_데이터 if li_데이터 is not None else None
                break

            # 서비스별 데이터 처리 - 요청일반
            elif s_서비스 == 'CNSRREQ' and 'cont_yn' in res:
                # 데이터 정의
                self.li_요청일반 = self.li_요청일반 + li_데이터
                print(f'proc_조건검색|{len(self.li_요청일반)}')

                # 추가 정보 확인
                s_검색식번호 = res.get('seq').replace(' ', '')
                s_연속조회여부 = res.get('cont_yn')
                s_연속조회키 = res.get('next_key')

                # 추가 조회 요청 - 연속조회 존재 시
                if s_연속조회여부 == 'Y':
                    await self.req_조건검색(s_데이터타입='요청일반',
                                        s_검색식번호=s_검색식번호, s_연속조회여부=s_연속조회여부, s_연속조회키=s_연속조회키)

                # 연속조회 없을 시 종료
                if s_연속조회여부 == 'N':
                    break

    async def run_조건검색(self, n_검색식번호=0):
        """ 웹소켓 실행함수 - 조건검색에 등록해 놓은 대상종목 리스트 수신 후 리턴 """
        # 웹소켓 서버 접속 및 수신대기 설정
        await self.api.ws_서버접속()
        task_수신대기 = asyncio.create_task(self.api.ws_메세지수신())
        await asyncio.sleep(1)

        # task 생성
        task_조건검색 = asyncio.create_task(self.proc_조건검색())

        # 요청 등록
        ret = await self.req_조건검색(s_데이터타입='목록조회')
        await asyncio.sleep(1)
        ret = await self.req_조건검색(s_데이터타입='요청실시간', s_검색식번호=str(n_검색식번호))

        # task 활성화
        await asyncio.gather(task_수신대기, task_조건검색)

        # 접속 종료
        await self.api.websocket.close()
        # await self.api.ws_접속해제()

        # 수신값 리턴
        return self.li_목록조회, self.li_요청실시간

    def get_조건검색(self, n_검색식번호=None):
        """ 조건검색에 등록된 대상종목 가져오기 """
        # 기준정보 정의
        dic_컬럼코드 = {'9001': '종목코드', '302': '종목명', '10': '현재가', '25': '전일대비기호', '11': '전일대비', '12': '등락율',
                    '13': '누적거래량', '16': '시가', '17': '고가', '18': '저가', 'jmcode': '종목코드'}
        n_검색식번호_조회 = n_검색식번호 if n_검색식번호 is not None else 0

        # 조검검색 실행 - 조회 실패 시 5회 재실행
        li_조건검색목록, li_검색종목 = (None, None)
        for _ in range(5):
            li_조건검색목록, li_검색종목 = asyncio.run(self.run_조건검색(n_검색식번호=n_검색식번호_조회))
            if li_검색종목 is None or len(li_검색종목) > 0:
                break
            time.sleep(1)

        # 데이터 처리 - 조건검색목록
        df_조검검색목록 = pd.DataFrame(li_조건검색목록)
        df_조검검색목록.columns = ['검색식번호', '검색식명']

        # 데이터 처리 - 대상종목
        df_검색종목 = pd.DataFrame(li_검색종목) if li_검색종목 is not None else pd.DataFrame()
        li_컬럼명 = [dic_컬럼코드[코드] for 코드 in df_검색종목.columns]
        df_검색종목.columns = li_컬럼명

        # if n_검색식번호 is None:
        #     return df_조검검색목록
        # elif b_목록포함:
        #     return df_조검검색목록, df_검색종목
        # else:
        #     return df_검색종목

        if n_검색식번호 is None:
            return df_조검검색목록
        else:
            return df_검색종목


if __name__ == '__main__':
    # ws = WebsocketAPIkiwoom()
    pass
