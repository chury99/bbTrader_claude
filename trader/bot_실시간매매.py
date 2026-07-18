import os
import re
import sys
import json
import time
from collections import deque

import pandas as pd
import multiprocessing as mp
import asyncio

import ut, xapi

# 매수세 전략 파라미터 (bot_백테스팅_틱기반매수세와 동일 - 환경변수로 동기 조정)
# 진입
_T_순매수비율 = float(os.environ.get('TB_RATIO', '0.4'))      # 60초 순매수비율 임계값 (매수세 형성)
_T_거래강도 = float(os.environ.get('TB_INT', '5.0'))          # 직전 5분 대비 60초 거래량 배수
_T_이격최소 = float(os.environ.get('TB_DIST', '5.0'))         # 당일고가 대비 최소 이격 % (눌림 필터)
_T_일최대거래 = int(os.environ.get('TB_MAXPERDAY', '2'))       # 종목당 1일 최대 진입 횟수
_T_쿨다운 = int(os.environ.get('TB_COOLDOWN', '600'))         # 청산 후 재진입 대기 (초)
# 청산
_T_손절 = float(os.environ.get('TB_STOP', '2.0'))            # 손절 % (매수가 대비)
_T_최소보유 = int(os.environ.get('TB_MINHOLD', '600'))        # 최소 보유시간 (초) - 이 동안은 손절만 작동
# 종목선정 (전일 일봉 기준)
_T_최소거래대금 = float(os.environ.get('TB_MINVALUE', '5000'))  # 전일 거래대금 하한 (백만원)
_T_최소가격 = float(os.environ.get('TB_MINPRICE', '1000'))     # 전일 종가 하한 (원)
# 실매매 전용 (총자산 균등 사이징 + 리스크 한계)
_T_분할수 = int(os.environ.get('TB_DIVISOR', '5'))            # 총자산 균등 분할 수 (진입당 매수금액 = 총자산 / 분할수)
_T_리스크캡 = float(os.environ.get('TB_RISKCAP', '1.0'))      # 거래당 리스크 한계 (총자본 %) - 손절 깊을 때만 실효(임계=분할수×리스크캡%)
_T_주문금액 = int(os.environ.get('TB_ORDERAMT', '500000'))     # 예수금/잔고 조회 실패 시 폴백 주문금액 (원)
_T_최대보유종목 = int(os.environ.get('TB_MAXPOS', '999'))      # 동시 보유 최대 종목 수 (기본 무제한 - 백테스팅 동일, 자본 제약 시 축소)
_T_주문타임아웃 = int(os.environ.get('TB_ORDTIMEOUT', '90'))   # 주문 후 체결 확인 대기 (초)


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming,PyTypeChecker,PyAttributeOutsideInit,PyUnresolvedReferences
class TraderBot:
    """ 틱 기반 매수세 실시간 매매 (백테스팅 bot_백테스팅_틱기반매수세와 동일 로직)
        - 진입: 매수세 형성 (60초 순매수비율/거래강도) + 눌림(당일고가 대비 이격) 필터
        - 청산: 매수세 소멸 (최소보유 이후) / 손절 / 장마감 """

    def __init__(self, queue_mp_수신2매매=None):
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
        self.folder_잔고 = dic_폴더정보['매수매도|종목잔고']
        os.makedirs(self.folder_잔고, exist_ok=True)
        self.folder_서버 = ('/Volumes/extSSD4tb/80_Backup/10_python_backup/ProjectWork/spTraderV2'
                          if sys.platform == 'darwin' else '')

        # api 정의 (주문용 - 웹소켓 데이터는 수신 모듈이 큐로 전달)
        self.restapi = xapi.RestAPI_kiwoom.RestAPIkiwoom()

        # queue 생성
        self.queue_mp_수신2매매 = queue_mp_수신2매매

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.fid_체결 = xapi.wsFID_kiwoom.fid_주식체결_0B()
        self.fid_주문 = xapi.wsFID_kiwoom.fid_주문체결_00()
        self.n_장마감초 = 15 * 3600 + 15 * 60    # 15:15 이후 신규진입 금지 + 보유분 청산
        self.tool = ut.도구manager.ToolManager()

        # 종목별 상태 정의
        self.set_매매대상 = set()      # 종목선정 통과 종목
        self.dic_종목명 = dict()
        self.dic_지표 = dict()         # 종목코드: dict(버킷=deque[(초,매수,매도)], 첫초, 직전고가)
        self.dic_포지션 = dict()       # 종목코드: dict(상태, 수량, 매수가, 매수초, 진입횟수, 청산초, 주문초, 매도재시도)
        self.path_포지션 = os.path.join(self.folder_잔고, f'dic_포지션_{self.s_오늘}.pkl')    # 재시작 복원용

        # 로그 기록
        self.make_로그(f'구동 시작 - 사이징(총자산÷{_T_분할수} 균등, 리스크캡 총자본 {_T_리스크캡:.1f}%/손절 {_T_손절:.1f}%), '
                     f'최대보유 {_T_최대보유종목}종목')

    # -----------------------------------------------------------------
    async def set_매매대상선정(self):
        """ 감시종목 중 전일 일봉 기준 매매 대상 선정 (백테스팅 pick_종목선정과 동일 필터) """
        # 감시종목 불러오기 (수신 모듈이 파일 생성 전이면 대기 - 기동 순서 레이스 방지)
        li_파일 = list()
        for _ in range(60):
            li_파일 = [파일 for 파일 in os.listdir(self.folder_감시종목)
                     if '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] <= self.s_오늘]
            if len(li_파일) > 0:
                break
            await asyncio.sleep(1)
        if len(li_파일) == 0:
            self.make_로그('감시종목 파일 미존재 - 매매대상 선정 중단')
            return
        dic_감시종목 = pd.read_pickle(os.path.join(self.folder_감시종목, max(li_파일)))
        li_감시종목 = dic_감시종목.get('매매대상', list()) + dic_감시종목.get('수집대상', list())

        # 전일 일봉 필터 (거래대금/가격)
        folder_일봉 = os.path.join(self.folder_서버, '데이터', '차트캐시', '일봉1')
        li_일봉파일 = sorted(파일 for 파일 in os.listdir(folder_일봉)
                        if '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] < self.s_오늘)
        dic_일봉 = pd.read_pickle(os.path.join(folder_일봉, li_일봉파일[-1])) if len(li_일봉파일) > 0 else dict()
        for s_종목코드 in li_감시종목:
            df_일봉 = dic_일봉.get(s_종목코드, None)
            if df_일봉 is None or len(df_일봉) == 0:
                continue
            sri_전일 = df_일봉.iloc[-1]
            if (sri_전일['거래대금(백만)'] >= _T_최소거래대금) and (sri_전일['종가'] >= _T_최소가격):
                self.set_매매대상.add(s_종목코드)
                self.dic_종목명[s_종목코드] = sri_전일['종목명']

        # 로그 기록
        self.make_로그(f'감시 {len(li_감시종목)}개 중 매매대상 {len(self.set_매매대상)}개 선정')

    # -----------------------------------------------------------------
    def _save_포지션(self):
        """ 포지션 상태를 당일 파일로 저장 (재시작 복원용) """
        try:
            pd.to_pickle(self.dic_포지션, self.path_포지션)
        except Exception as e:
            print(f'포지션 저장 실패 - {e}', file=sys.stderr)

    # -----------------------------------------------------------------
    def restore_포지션(self):
        """ 봇 재시작 시 포지션 복원 - 당일 포지션 파일과 계좌잔고 대조
            (파일에 기록된 전략 포지션만 복원, 잔고에만 있는 수동 보유는 건드리지 않음) """
        # 당일 포지션 파일 확인 (없으면 정상 기동 - 복원 불필요)
        if not os.path.exists(self.path_포지션):
            return
        try:
            dic_포지션_파일 = pd.read_pickle(self.path_포지션)
        except Exception as e:
            self.make_로그(f'포지션 파일 로딩 실패 - 복원 생략 - {e}')
            return
        if len(dic_포지션_파일) == 0:
            return

        # 계좌잔고 조회 (실제 보유 확인)
        try:
            dic_계좌잔고, df_종목별잔고 = self.restapi.tr_체결잔고요청()
            dic_잔고 = (df_종목별잔고.set_index('종목코드')['현재잔고'].to_dict()
                      if len(df_종목별잔고) > 0 else dict())
        except Exception as e:
            self.make_로그(f'잔고조회 실패 - 포지션 복원 생략 (수동 확인 필요) - {e}')
            return

        # 파일 기록과 잔고 대조 후 복원
        li_복원, li_정리 = list(), list()
        for s_종목코드, dic_기록 in dic_포지션_파일.items():
            n_잔고수량 = int(dic_잔고.get(s_종목코드, 0))
            b_보유기록 = dic_기록.get('상태') in ['매수중', '보유', '매도중'] and dic_기록.get('수량', 0) >= 0

            # 기록상 보유(진행) + 실제 잔고 있음 -> 보유 복원 (수량은 실제 잔고 기준)
            if b_보유기록 and n_잔고수량 > 0:
                dic_기록.update(상태='보유', 수량=n_잔고수량, 매도재시도=0)
                self.dic_포지션[s_종목코드] = dic_기록
                self.set_매매대상.add(s_종목코드)    # 청산 감시를 위해 대상 유지
                li_복원.append(f'{s_종목코드}({n_잔고수량}주)')

            # 기록상 보유였으나 잔고 없음 -> 이미 청산됨 (진입횟수/청산이력은 유지)
            else:
                dic_기록.update(상태='없음', 수량=0)
                self.dic_포지션[s_종목코드] = dic_기록
                li_정리.append(s_종목코드)

        # 잔고에만 있는 종목 - 전략 기록 없음 -> 수동 보유로 간주, 미개입 (로그만)
        li_수동보유 = [코드 for 코드, 수량 in dic_잔고.items()
                   if 수량 > 0 and 코드 not in dic_포지션_파일]

        # 로그 기록
        self.make_로그(f'포지션 복원 - 보유 {len(li_복원)}건 {li_복원}\n'
                     f' - 청산확인 {len(li_정리)}건, 수동보유(미개입) {len(li_수동보유)}건 {li_수동보유}')
        self._save_포지션()

    # -----------------------------------------------------------------
    async def exec_종목감시(self):
        """ 큐에서 들어오는 체결/주문 데이터 대상으로 매매조건 감시 및 주문 """
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
            except (TypeError, KeyError):
                continue

            # 데이터 타입별 처리
            try:
                if s_데이터타입 == '주식체결':
                    self._proc_체결틱(s_종목코드=s_종목코드, dic_값=dic_데이터_변동)
                elif s_데이터타입 == '주문체결':
                    self._proc_주문체결(s_종목코드=s_종목코드, dic_값=dic_데이터_변동)
            except Exception as e:
                print(f'매매처리 오류 - {s_종목코드} - {e}', file=sys.stderr)

    # -----------------------------------------------------------------
    def _proc_체결틱(self, s_종목코드, dic_값):
        """ 주식체결 틱 처리 - 지표 업데이트 후 진입/청산 판단 (백테스팅과 동일 지표) """
        # 매매대상 외 종목 제외
        if s_종목코드 not in self.set_매매대상:
            return

        # 틱 데이터 파싱
        fid = self.fid_체결.dic_이름2코드
        try:
            s_시간 = str(dic_값[fid['체결시간']]).strip()
            n_초 = int(s_시간[:2]) * 3600 + int(s_시간[2:4]) * 60 + int(s_시간[4:6])
            n_현재가 = abs(int(dic_값[fid['현재가']]))
            n_거래량 = int(dic_값[fid['거래량']])            # 부호: +매수 / -매도
            n_당일고가 = abs(int(dic_값[fid['고가']]))
        except (KeyError, ValueError, IndexError):
            return

        # 지표 상태 초기화
        dic_지표 = self.dic_지표.setdefault(
            s_종목코드, dict(버킷=deque(), 첫초=n_초, 직전고가=n_당일고가, 직전가=n_현재가, 판정초=0))

        # 주문 타임아웃 안전장치 (시장가 미체결 방지)
        dic_포지션 = self.dic_포지션.setdefault(
            s_종목코드, dict(상태='없음', 수량=0, 매수가=0, 매수초=0, 진입횟수=0, 청산초=0, 주문초=0, 매도재시도=0))
        if dic_포지션['상태'] == '매수중' and n_초 - dic_포지션['주문초'] > _T_주문타임아웃:
            self.make_로그(f'매수 체결확인 실패 - {s_종목코드} - 상태 초기화')
            dic_포지션['상태'] = '없음'
            self._save_포지션()
        if dic_포지션['상태'] == '매도중' and n_초 - dic_포지션['주문초'] > _T_주문타임아웃:
            if dic_포지션['매도재시도'] < 3:
                dic_포지션['매도재시도'] += 1
                self.make_로그(f'매도 체결확인 실패 - {s_종목코드} - 재시도 {dic_포지션["매도재시도"]}회')
                self._send_매도(s_종목코드=s_종목코드, dic_포지션=dic_포지션, n_초=n_초, s_사유='재시도')

        # 판정 실행 - 직전 틱 이후 경과한 모든 완결초를 순차 판정 (백테스팅의 매초 1초봉 판정과 동일 의미)
        # (거래 없는 초에도 윈도우 경계 이동으로 신호가 발생할 수 있음 - 체결은 현재 틱 가격)
        buk = dic_지표['버킷']
        if len(buk) > 0 and n_초 > buk[-1][0]:
            n_시작초 = max(dic_지표['판정초'] + 1, dic_지표['첫초'] + 361)
            for n_완결초 in range(n_시작초, n_초):
                self._judge_바(s_종목코드=s_종목코드, dic_지표=dic_지표, n_완결초=n_완결초, n_주문참고가=n_현재가)
            dic_지표['판정초'] = n_초 - 1

        # 윈도우 버킷 업데이트 (초 단위 합산)
        n_매수량 = n_거래량 if n_거래량 > 0 else 0
        n_매도량 = -n_거래량 if n_거래량 < 0 else 0
        if len(buk) > 0 and buk[-1][0] == n_초:
            buk[-1][1] += n_매수량
            buk[-1][2] += n_매도량
        else:
            buk.append([n_초, n_매수량, n_매도량])
        while len(buk) > 0 and buk[0][0] < n_초 - 720:    # 보수적 유지 (판정 윈도우는 합산 시 명시적 경계 사용)
            buk.popleft()
        dic_지표['직전고가'] = n_당일고가    # 다음 판정용 (백테스팅 shift(1)과 동일)
        dic_지표['직전가'] = n_현재가

    # -----------------------------------------------------------------
    def _judge_바(self, s_종목코드, dic_지표, n_완결초, n_주문참고가):
        """ 완결초 하나에 대한 매매 판정 (백테스팅 1초봉 판정과 동일 정의) """
        # 매수세 지표 계산
        buk = dic_지표['버킷']
        n_매수60 = sum(b[1] for b in buk if n_완결초 - 60 < b[0] <= n_완결초)
        n_매도60 = sum(b[2] for b in buk if n_완결초 - 60 < b[0] <= n_완결초)
        n_전체60 = n_매수60 + n_매도60
        n_전체300 = sum(b[1] + b[2] for b in buk
                      if n_완결초 - 360 < b[0] <= n_완결초 - 60)    # 직전 300초 (60~360초 전)
        n_순매수비율 = (n_매수60 - n_매도60) / n_전체60 if n_전체60 > 0 else 0
        n_거래강도 = n_전체60 / (n_전체300 / 5) if n_전체300 > 0 else 0
        n_판정가 = dic_지표['직전가']          # 완결초까지의 마지막 체결가 (백테스팅 ffill과 동일)
        n_이격률 = ((dic_지표['직전고가'] - n_판정가) / dic_지표['직전고가'] * 100
                 if dic_지표['직전고가'] > 0 else 0)

        # 포지션 상태 확인
        dic_포지션 = self.dic_포지션.setdefault(
            s_종목코드, dict(상태='없음', 수량=0, 매수가=0, 매수초=0, 진입횟수=0, 청산초=0, 주문초=0, 매도재시도=0))

        # 청산 판단 (보유 시) - 손절도 완결초 가격 기준 (백테스팅과 동일)
        if dic_포지션['상태'] == '보유':
            n_경과 = n_완결초 - dic_포지션['매수초']
            b_손절 = n_판정가 <= dic_포지션['매수가'] * (1 - _T_손절 / 100)
            b_소멸 = (n_경과 >= _T_최소보유) and (n_순매수비율 < 0)
            b_마감 = n_완결초 >= self.n_장마감초
            if b_손절 or b_소멸 or b_마감:
                s_사유 = '손절' if b_손절 else '소멸' if b_소멸 else '마감'
                self._send_매도(s_종목코드=s_종목코드, dic_포지션=dic_포지션, n_초=n_완결초, s_사유=s_사유)

        # 진입 판단 (미보유 시)
        elif dic_포지션['상태'] == '없음':
            n_보유종목수 = sum(1 for p in self.dic_포지션.values() if p['상태'] in ['매수중', '보유', '매도중'])
            b_진입 = ((n_순매수비율 > _T_순매수비율)
                    and (n_거래강도 > _T_거래강도)
                    and (n_이격률 >= _T_이격최소)
                    and (n_완결초 < self.n_장마감초)
                    and (dic_포지션['진입횟수'] < _T_일최대거래)
                    and (n_완결초 >= dic_포지션['청산초'] + _T_쿨다운)
                    and (n_보유종목수 < _T_최대보유종목))
            if b_진입:
                self._send_매수(s_종목코드=s_종목코드, dic_포지션=dic_포지션, n_초=n_완결초, n_현재가=n_주문참고가)

    # -----------------------------------------------------------------
    def _calc_매수금액(self):
        """ 총자산 균등 주문금액 산정 (진입 신호 시점의 계좌잔고 조회)
            총자본   = 예수금(현금) + 보유주식 평가금액 합
            목표금액 = 총자본 ÷ 분할수(5)                    -> 진입마다 총자산의 1/5 균등 배분
            리스크캡 = 총자본 × 리스크캡%(1%) ÷ 손절률%       -> 손절 시 손실이 총자본의 1% 이내
            매수금액 = min(목표금액, 리스크캡, 예수금)         -> 균등배분/리스크한계/가용현금 중 최소
            (손절 2% + ÷5 이면 거래당 리스크는 총자본의 0.4%로 캡(1%) 미달 → 캡은 손절>5%에서만 실효)
            잔고 조회 실패 시 폴백 주문금액(_T_주문금액) 사용 """
        try:
            dic_계좌잔고, df_종목별잔고 = self.restapi.tr_체결잔고요청()
            n_예수금 = int(dic_계좌잔고.get('n_d2예수금', 0))
            n_평가금액 = int(df_종목별잔고['평가금액'].sum()) if len(df_종목별잔고) > 0 else 0
        except Exception as e:
            self.make_로그(f'잔고 조회 실패 - 폴백 주문금액 {_T_주문금액:,}원 사용 - {e}')
            return _T_주문금액
        n_총자본 = n_예수금 + n_평가금액
        if n_총자본 <= 0 or n_예수금 <= 0:
            return 0
        n_목표금액 = n_총자본 / _T_분할수 if _T_분할수 > 0 else n_총자본   # 분할수 0 방어
        n_리스크캡 = n_총자본 * _T_리스크캡 / 100 / (_T_손절 / 100) if _T_손절 > 0 else n_목표금액
        return int(min(n_목표금액, n_리스크캡, n_예수금))   # 균등배분/리스크한계/가용현금 중 최소

    def _send_매수(self, s_종목코드, dic_포지션, n_초, n_현재가):
        """ 시장가 매수 주문 송신 (리스크 기반 사이징) """
        # 주문수량 산정 - 예수금 기반 리스크 사이징
        n_매수금액 = self._calc_매수금액()
        if n_매수금액 < n_현재가:
            self.make_로그(f'매수 보류 - {self.dic_종목명.get(s_종목코드, s_종목코드)}({s_종목코드}) '
                         f'주문금액 {n_매수금액:,}원 < 현재가 {n_현재가:,}원 (예수금 부족/조회실패)')
            return
        n_수량 = max(1, int(n_매수금액 // n_현재가))

        # 주문 송신
        res = self.restapi.tr_주식주문(s_구분='매수', s_종목코드=s_종목코드,
                                   n_주문수량=n_수량, n_주문단가=0, s_매매구분='시장가')

        # 상태 업데이트
        if isinstance(res, dict) and res.get('return_code') == 0:
            dic_포지션.update(상태='매수중', 주문초=n_초, 매수초=n_초, 매수가=n_현재가, 매도재시도=0)
            dic_포지션['진입횟수'] += 1
            self.make_로그(f'매수주문 - {self.dic_종목명.get(s_종목코드, s_종목코드)}({s_종목코드}) '
                         f'{n_수량}주 @{n_현재가:,} (약 {n_수량 * n_현재가:,}원, 시장가)')
            self._save_포지션()
        else:
            self.make_로그(f'매수주문 실패 - {s_종목코드} - {res}')

    # -----------------------------------------------------------------
    def _send_매도(self, s_종목코드, dic_포지션, n_초, s_사유):
        """ 시장가 매도 주문 송신 (보유 전량) """
        # 수량 확인
        n_수량 = dic_포지션['수량']
        if n_수량 <= 0:
            dic_포지션['상태'] = '없음'
            return

        # 주문 송신
        res = self.restapi.tr_주식주문(s_구분='매도', s_종목코드=s_종목코드,
                                   n_주문수량=n_수량, n_주문단가=0, s_매매구분='시장가')

        # 상태 업데이트
        if isinstance(res, dict) and res.get('return_code') == 0:
            dic_포지션.update(상태='매도중', 주문초=n_초)
            self.make_로그(f'매도주문({s_사유}) - {self.dic_종목명.get(s_종목코드, s_종목코드)}({s_종목코드}) '
                         f'{n_수량}주 (시장가)')
            self._save_포지션()
        else:
            self.make_로그(f'매도주문 실패 - {s_종목코드} - {res}')

    # -----------------------------------------------------------------
    def _proc_주문체결(self, s_종목코드, dic_값):
        """ 주문체결 수신 처리 - 체결 확인 후 포지션 상태 업데이트 """
        fid = self.fid_주문.dic_이름2코드
        # 종목코드 확인 (FID 우선, 'A' 접두 제거)
        s_코드 = str(dic_값.get(fid['종목코드'], s_종목코드)).strip().lstrip('A')
        if s_코드 not in self.dic_포지션:
            return
        dic_포지션 = self.dic_포지션[s_코드]

        # 체결 상태만 처리
        s_주문상태 = str(dic_값.get(fid['주문상태'], '')).strip()
        if s_주문상태 != '체결':
            return

        # 체결 정보 파싱
        try:
            s_매도수 = self.fid_주문.dic_매도수구분.get(str(dic_값.get(fid['매도수구분'], '')).strip(), '')
            n_체결량 = abs(int(str(dic_값.get(fid['체결량'], '0')).strip() or 0))
            n_체결가 = abs(int(str(dic_값.get(fid['체결가'], '0')).strip() or 0))
            n_미체결 = abs(int(str(dic_값.get(fid['미체결수량'], '0')).strip() or 0))
        except (ValueError, TypeError):
            return

        # 매수 체결 - 보유 확정
        if s_매도수 == '매수' and dic_포지션['상태'] in ['매수중', '보유']:
            dic_포지션['수량'] += n_체결량
            dic_포지션['매수가'] = n_체결가 if n_체결가 > 0 else dic_포지션['매수가']
            dic_포지션['상태'] = '보유'
            self.make_로그(f'매수체결 - {self.dic_종목명.get(s_코드, s_코드)}({s_코드}) '
                         f'{n_체결량}주 @{n_체결가:,} (보유 {dic_포지션["수량"]}주)')
            self._save_포지션()

        # 매도 체결 - 청산 확정
        elif s_매도수 == '매도' and dic_포지션['상태'] == '매도중':
            dic_포지션['수량'] = max(0, dic_포지션['수량'] - n_체결량)
            self.make_로그(f'매도체결 - {self.dic_종목명.get(s_코드, s_코드)}({s_코드}) '
                         f'{n_체결량}주 @{n_체결가:,} (잔여 {dic_포지션["수량"]}주)')
            if n_미체결 == 0 or dic_포지션['수량'] == 0:
                n_수익률 = (n_체결가 / dic_포지션['매수가'] - 1) * 100 if dic_포지션['매수가'] > 0 else 0
                dic_포지션.update(상태='없음', 수량=0, 청산초=pd.Timestamp.now().hour * 3600
                                + pd.Timestamp.now().minute * 60 + pd.Timestamp.now().second)
                self.make_로그(f'청산완료 - {self.dic_종목명.get(s_코드, s_코드)}({s_코드}) '
                             f'수익률 {n_수익률:+.2f}% (비용 전)')
            self._save_포지션()

    # -----------------------------------------------------------------
    async def run_실시간매매(self):
        """ exec 함수들을 비동기로 구동 """
        # 매매대상 선정 및 포지션 복원(재시작 대비) 후 감시 시작
        await self.set_매매대상선정()
        self.restore_포지션()
        await asyncio.gather(
            self.exec_종목감시()
        )


# noinspection SpellCheckingInspection,PyPep8Naming,NonAsciiCharacters
def run(queue_mp_수신2매매=None):
    queue_mp_수신2매매 = queue_mp_수신2매매 if queue_mp_수신2매매 is not None else mp.Queue()
    t = TraderBot(queue_mp_수신2매매=queue_mp_수신2매매)
    asyncio.run(t.run_실시간매매())


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
