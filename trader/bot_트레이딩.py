import os
import sys
import time
import re

import pandas as pd

import ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming
class TraderBot:
    # noinspection PyUnresolvedReferences
    def __init__(self):
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
        self.folder_work = dic_폴더정보['folder_work']
        self.folder_종목잔고 = dic_폴더정보['매수매도|종목잔고']
        self.folder_신호탐색 = dic_폴더정보['매수매도|신호탐색']
        os.makedirs(self.folder_종목잔고, exist_ok=True)
        os.makedirs(self.folder_신호탐색, exist_ok=True)

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.s_종료시각 = dic_config['종료시각']
        self.n_tr딜레이 = 0.2
        self.s_계좌번호 = str(dic_config['계좌번호'])
        self.n_손절수익률 = int(dic_config['손절수익률'])
        self.n_익절수익률 = int(dic_config['익절수익률'])

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)
        '''
        dic_계좌잔고, df_종목별잔고 = self.api.tr_체결잔고요청()
        df_일봉 = self.api.tr_주식일봉차트조회요청(s_종목코드='000020', s_시작일자=None, s_종료일자=None)
        df_분봉 = self.api.tr_주식분봉차트조회요청(s_종목코드='000020', s_틱범위='1')
        df_종목별주가 = self.api.tr_업종별주가요청(s_시장='코스피')
        df_실시간조회순위 = self.api.tr_실시간종목조회순위()
        res = self.api.tr_주식주문(s_구분='매수', s_종목코드='319400', n_주문수량=1, n_주문단가=6590, s_매매구분='IOC보통')
        '''

        # 보유종목 확인
        self.dic_계좌잔고, self.df_종목별잔고, self.dic_종목코드2종목명 = self._get_종목별잔고()
        time.sleep(self.n_tr딜레이)

        # 일봉 고가 확인
        folder_일봉캐시 = os.path.join(self.folder_work.replace('bbTrader', 'spTraderV2'), '데이터', '차트캐시', '일봉1')
        file_일봉캐시 = max(파일 for 파일 in os.listdir(folder_일봉캐시)
                            if '.pkl' in 파일 and re.findall(r'\d{8}', 파일)[0] < self.s_오늘)
        dic_일봉 = pd.read_pickle(os.path.join(folder_일봉캐시, file_일봉캐시))
        li_보유종목 = self.df_종목별잔고['종목코드'].tolist() if not self.df_종목별잔고.empty else list()
        self.dic_일봉고가 = {종목코드 : max(일봉['고가'][-5:]) for 종목코드, 일봉 in dic_일봉.items() if 종목코드 in li_보유종목}

        # 로그 기록
        self.make_로그(f'구동 시작')

    def avtivate_종목감시(self):
        """ 보유종목 기준으로 3분봉 감시 """
        # 신호 초기화
        b_탐색신호_분봉 = False
        b_탐색신호_초봉 = False
        b_매도신호 = False
        s_탐색시점 = '00:00:00'
        df_매도신호 = pd.DataFrame()
        li_매도종목 = list()

        # 감시 루프 생성
        while True:
            # 탐색신호 확인
            dt_현재 = pd.Timestamp.now()
            if dt_현재.strftime('%H:%M:%S') != s_탐색시점:
                b_탐색신호_분봉 = (not b_탐색신호_분봉) and (dt_현재.minute % 3 == 0) and (dt_현재.second == 1)
                b_탐색신호_초봉 = (not b_탐색신호_초봉) and (dt_현재.second % 5 == 1)
                s_탐색시점 = dt_현재.strftime('%H:%M:%S')

            # 신호 탐색
            if b_탐색신호_분봉 or b_탐색신호_초봉:
                # 매도신호 생성
                li_보유종목 = self.df_종목별잔고['종목코드'].tolist() if not self.df_종목별잔고.empty else list()
                df_매도신호 = self.check_매도신호_분봉(li_대상종목=li_보유종목) if b_탐색신호_분봉\
                        else self.check_매도신호_초봉(li_대상종목=li_보유종목) if b_탐색신호_초봉 else pd.DataFrame()
                li_매도종목 = df_매도신호.loc[df_매도신호['매도신호'], '종목코드'].to_list() if not df_매도신호.empty else list()
                b_매도신호 = len(li_매도종목) > 0

                # 매도신호 저장
                if len(df_매도신호) > 0 and b_탐색신호_분봉:
                    # 데이터 재정리
                    df_매도신호['일자'] = self.s_오늘
                    df_매도신호['시간'] = s_탐색시점
                    li_컬럼명 = ['일자', '시간'] + [컬럼 for 컬럼 in df_매도신호.columns if 컬럼 not in ['일자', '시간']]
                    df_매도신호 = df_매도신호.loc[:, li_컬럼명]

                    # 데이터 저장
                    path_매도신호 = os.path.join(self.folder_신호탐색, f'df_매도신호_{self.s_오늘}.csv')
                    li_li매도신호 = df_매도신호.values.tolist()
                    li_li매도신호 = [list(df_매도신호.columns)] + li_li매도신호 if not os.path.exists(path_매도신호)\
                                    else li_li매도신호
                    with open(path_매도신호, mode='at', encoding='cp949') as f:
                        for li_데이터 in li_li매도신호:
                            li_데이터 = [str(데이터) for 데이터 in li_데이터]
                            f.write(f'{','.join(li_데이터)}\n')

                # 로그 기록
                if b_탐색신호_분봉:
                    s_로그 = f'매도탐색-{len(self.df_종목별잔고)}종목'
                    for s_종목코드 in li_보유종목:
                        b_매도신호존재 = s_종목코드 in df_매도신호.index
                        s_종목명 = df_매도신호.loc[s_종목코드, '종목명'] if b_매도신호존재 else None
                        s_매도이력 = ('매도o' if df_매도신호.loc[s_종목코드, '매도이력'] else '매도x') if b_매도신호존재 else None
                        s_고가터치 = ('고가o' if df_매도신호.loc[s_종목코드, '고가터치'] else '고가x') if b_매도신호존재 else None
                        n_종가 = df_매도신호.loc[s_종목코드, '종가1'] if b_매도신호존재 else 0
                        n_수익률 = df_매도신호.loc[s_종목코드, '수익률'] if b_매도신호존재 else 0
                        n_고가 = df_매도신호.loc[s_종목코드, '당일고가'] if b_매도신호존재 else 0
                        n_손절가 = df_매도신호.loc[s_종목코드, '손절기준가'] if b_매도신호존재 else 0
                        n_익절가 = df_매도신호.loc[s_종목코드, '익절기준가'] if b_매도신호존재 else 0
                        n_저가3봉 = df_매도신호.loc[s_종목코드, '저가3봉'] if b_매도신호존재 else 0
                        s_로그 = (s_로그 +
                                f'\n - {s_종목명}({s_종목코드}), {s_매도이력}, {s_고가터치}, 종가 {n_종가:,.0f}({n_수익률:.1f}%)'
                                f'\n      고가 {n_고가:,.0f}, 손절 {n_손절가:,.0f}, 익절 {n_익절가:,.0f}, 저가3 {n_저가3봉:,.0f}')
                    self.make_로그(s_로그)

                # 탐색신호 초기화
                b_탐색신호_분봉 = False
                b_탐색신호_초봉 = False

            # 매도 요청
            if b_매도신호:
                # 매도종목 확인
                for s_종목코드 in li_매도종목:
                    # 종목정보 업데이트
                    self.dic_계좌잔고, self.df_종목별잔고, self.dic_종목코드2종목명 = self._get_종목별잔고()
                    time.sleep(self.n_tr딜레이)
                    s_종목명 = self.df_종목별잔고.loc[s_종목코드, '종목명']
                    n_현재잔고 = self.df_종목별잔고.loc[s_종목코드, '현재잔고']
                    n_매수가 = self.df_종목별잔고.loc[s_종목코드, '매입단가']
                    n_현재가 = self.df_종목별잔고.loc[s_종목코드, '현재가']
                    s_매도사유 = df_매도신호.loc[s_종목코드, '매도사유']

                    # 매도주문 요청
                    n_주문수량 = int(n_현재잔고 / 2) if s_매도사유 == '목표달성' else n_현재잔고
                    n_주문단가 = self.tool.find_주문단가(n_기준가=n_현재가, n_틱보정=-5)
                    s_매매구분 = 'IOC보통'
                    ret_주문 = self.api.tr_주식주문(s_구분='매도', s_종목코드=s_종목코드, n_주문수량=n_주문수량, n_주문단가=n_주문단가, s_매매구분=s_매매구분)
                    time.sleep(self.n_tr딜레이)

                    # 로그 기록
                    self.make_로그(f'매도주문\n'
                                 f' - {s_매도사유} | {s_종목명}({s_종목코드}) {n_매수가:,.0f} -> {n_주문단가:,.0f}원 {n_주문수량:,.0f}주\n'
                                 f'{ret_주문}')

                # 매도신호 초기화
                b_매도신호 = False

                # 보유종목 업데이트
                self.dic_계좌잔고, self.df_종목별잔고, self.dic_종목코드2종목명 = self._get_종목별잔고()
                time.sleep(self.n_tr딜레이)

            # 종료시각 확인
            if dt_현재 > pd.Timestamp(self.s_종료시각):
                break

            # 감시주기 설정
            time.sleep(0.2)

    def check_매도신호_분봉(self, li_대상종목):
        """ 보유 종목의 매도신호 확인해서 리턴 """
        # 매도이력 확인
        dic_전체손익, df_매매일지 = self.api.tr_당일매매일지요청(s_조회일자=self.s_오늘)
        time.sleep(self.n_tr딜레이)
        li_당일매도 = df_매매일지.loc[df_매매일지['매도수량'] > 0, '종목코드'].to_list() if not df_매매일지.empty else list()

        # 종목별 데이터 확인
        li_dic매도신호 = list()
        for s_종목코드 in li_대상종목:
            # 공통 데이터 확인
            s_현재시간 = pd.Timestamp.now().strftime('%H:%M:%S')
            s_종목명 = self.dic_종목코드2종목명[s_종목코드]
            n_매수가 = self.df_종목별잔고.loc[s_종목코드, '매입단가']
            n_일봉고가 = self.dic_일봉고가.get(s_종목코드, 0)
            n_일봉고가수익률 = (n_일봉고가 / n_매수가 - 1) * 100 - 0.2

            # 3분봉 준비
            df_분봉 = self.api.tr_주식분봉차트조회요청(s_종목코드=s_종목코드, s_틱범위='3')
            time.sleep(self.n_tr딜레이)
            if df_분봉.empty: continue
            df_분봉 = df_분봉.loc[df_분봉['일자'] == self.s_오늘].sort_values('시간')
            df_분봉 = df_분봉.loc[df_분봉['시간'] < pd.Timestamp.now().floor('3min').strftime('%H:%M:%S')]
            if df_분봉.empty: continue

            # 추가지표 생성
            df_분봉['고저'] = df_분봉['고가'] - df_분봉['저가']
            df_분봉['고종가1'] = (df_분봉['고가'] - df_분봉['종가'].shift(1)).abs()
            df_분봉['저종가1'] = (df_분봉['저가'] - df_분봉['종가'].shift(1)).abs()
            df_분봉['ATR'] = df_분봉[['고저', '고종가1', '저종가1']].max(axis=1)
            df_분봉['ATR14'] = df_분봉['ATR'].ewm(alpha=1/14, adjust=False).mean()

            # 데이터 생성
            n_시가1 = df_분봉['시가'].values[-1]
            n_종가1 = df_분봉['종가'].values[-1]
            n_비디1 = (n_종가1 - n_시가1) / n_시가1 * 100
            n_당일고가 = df_분봉['고가'].max()
            n_저가3봉 = df_분봉['저가'].values[-4:-1].min() if len(df_분봉) >= 4 else df_분봉['저가'].min()
            n_수익률1 = (n_종가1 / n_매수가 - 1) * 100 - 0.2
            n_고가수익률 = (n_당일고가 / n_매수가 - 1) * 100 - 0.2
            n_ATR14 = df_분봉['ATR14'].values[-1] if not pd.isna(df_분봉['ATR14'].values[-1]) else None

            # 매도신호 확인 - 목표수익률 달성 시 절반 매도  ====> tr_당일매매일지요청 사용해서 매매이력 있는지 확인
            b_매도이력 = s_종목코드 in li_당일매도
            b_고가터치 = (n_고가수익률 > self.n_익절수익률) or (n_당일고가 >= n_일봉고가 and n_일봉고가수익률 > 5)
            b_목표달성 = b_고가터치 and not b_매도이력

            # 매도신호 확인 - 익절
            n_익절기준가 = n_당일고가 - 2 * n_ATR14 if n_ATR14 is not None else 0
            b_고가이탈 = n_종가1 < n_익절기준가 if n_ATR14 is not None else n_종가1 < n_저가3봉
            b_익절 = b_고가터치 and b_고가이탈 and (n_비디1 < 0)

            # 매도신호 확인 - 손절
            n_손절기준가 = n_매수가 * (100 - self.n_손절수익률 - 0.2) / 100
            b_손절 = (n_종가1 < n_손절기준가) and (n_비디1 < 0) and (s_현재시간 > '09:00:00')

            # 결과 정리
            b_매도신호 = b_목표달성 or b_익절 or b_손절
            s_매도사유 = '목표달성' if b_목표달성 else '익절' if b_익절 else '손절' if b_손절 else '-'
            dic_매도신호 = dict(종목코드=s_종목코드, 종목명=s_종목명, 매도신호=b_매도신호, 매도사유=s_매도사유)
            dic_매도신호.update(매수가=n_매수가, 종가1=n_종가1, 매도이력=b_매도이력, 고가터치=b_고가터치,
                            수익률=n_수익률1, 고가수익률=n_고가수익률, 익절기준가=n_익절기준가, 손절기준가=n_손절기준가,
                            당일고가=n_당일고가, 저가3봉=n_저가3봉, ATR14=n_ATR14,
                            익절수익률=self.n_익절수익률, 손절수익률=self.n_손절수익률)
            li_dic매도신호.append(dic_매도신호)

        # df 정리
        df_매도신호 = pd.DataFrame(li_dic매도신호) if len(li_dic매도신호) > 0 else pd.DataFrame()
        df_매도신호 = df_매도신호.set_index('종목코드', drop=False) if not df_매도신호.empty else df_매도신호

        return df_매도신호

    def check_매도신호_초봉(self, li_대상종목):
        """ 보유 종목의 매도신호 확인해서 리턴 """
        # 종목정보 업데이트
        self.dic_계좌잔고, self.df_종목별잔고, self.dic_종목코드2종목명 = self._get_종목별잔고()
        time.sleep(self.n_tr딜레이)
        dic_실시간수익률 = self.df_종목별잔고.set_index('종목코드')['손익률'].to_dict() if len(self.df_종목별잔고) > 0 else dict()

        # 매도이력 확인
        dic_전체손익, df_매매일지 = self.api.tr_당일매매일지요청(s_조회일자=self.s_오늘)
        time.sleep(self.n_tr딜레이)
        li_당일매도 = df_매매일지.loc[df_매매일지['매도수량'] > 0, '종목코드'].to_list() if not df_매매일지.empty else list()

        # 종목별 데이터 확인
        li_dic매도신호 = list()
        for s_종목코드 in li_대상종목:
            # 종목정보 미존재 시 업데이트
            if s_종목코드 not in self.df_종목별잔고.index:
                self.dic_계좌잔고, self.df_종목별잔고, self.dic_종목코드2종목명 = self._get_종목별잔고()
                time.sleep(self.n_tr딜레이)

            # 공통 데이터 확인
            s_종목명 = self.dic_종목코드2종목명.get(s_종목코드, None)
            n_매수가 = self.df_종목별잔고.loc[s_종목코드, '매입단가']
            n_일봉고가 = self.dic_일봉고가.get(s_종목코드, 0)
            n_일봉고가수익률 = (n_일봉고가 / n_매수가 - 1) * 100 - 0.2

            # 매도신호 확인 - 목표수익률 달성 시 절반 매도  ====> tr_당일매매일지요청 사용해서 매매이력 있는지 확인
            b_목표달성 = False
            n_실시간수익률 = dic_실시간수익률.get(s_종목코드, 0)
            if n_실시간수익률 > (self.n_익절수익률 - 1):
                df_분봉 = self.api.tr_주식분봉차트조회요청(s_종목코드=s_종목코드, s_틱범위='3')
                time.sleep(self.n_tr딜레이)
                if df_분봉.empty: continue
                n_당일고가_실시간 = df_분봉.loc[df_분봉['일자'] == self.s_오늘, '고가'].max()
                n_고가수익률_실시간 = (n_당일고가_실시간 / n_매수가 - 1) * 100 - 0.2
                b_매도이력 = s_종목코드 in li_당일매도
                b_고가터치 = (n_고가수익률_실시간 > self.n_익절수익률) or (n_당일고가_실시간 >= n_일봉고가 and n_일봉고가수익률 > 5)
                b_목표달성 = b_고가터치 and not b_매도이력

            # 매도신호 확인 - 익절
            b_익절 = False

            # 매도신호 확인 - 손절
            b_손절 = False

            # 결과 정리
            b_매도신호 = b_목표달성 or b_익절 or b_손절
            s_매도사유 = '목표달성' if b_목표달성 else '익절' if b_익절 else '손절' if b_손절 else '-'
            dic_매도신호 = dict(종목코드=s_종목코드, 종목명=s_종목명, 매도신호=b_매도신호, 매도사유=s_매도사유)
            dic_매도신호.update(매수가=n_매수가, 익절수익률=self.n_익절수익률, 손절수익률=self.n_손절수익률)
            li_dic매도신호.append(dic_매도신호)

        # df 정리
        df_매도신호 = pd.DataFrame(li_dic매도신호) if len(li_dic매도신호) > 0 else pd.DataFrame()
        df_매도신호 = df_매도신호.set_index('종목코드', drop=False) if not df_매도신호.empty else df_매도신호

        return df_매도신호

    def _get_종목별잔고(self):
        """ 종목별 잔고 조회하여 df 리턴 """
        # 체결잔고 조회
        dic_계좌잔고, df_종목별잔고 = self.api.tr_체결잔고요청()
        if df_종목별잔고.empty:
            return dic_계좌잔고, df_종목별잔고, dict()

        # 데이터 정리
        df_종목별잔고['종목코드'] = df_종목별잔고['종목코드'].str.replace('A', '')
        df_종목별잔고 = df_종목별잔고.set_index('종목코드', drop=False)
        dic_종목코드2종목명 = df_종목별잔고['종목명'].to_dict()

        # 추가 데이터 설정
        li_종가매수일, li_보유기간 = self._check_보유기간(df_종목별잔고['종목코드'].tolist())
        df_종목별잔고['종가매수일'] = li_종가매수일
        df_종목별잔고['보유기간'] = li_보유기간
        df_종목별잔고['조회일자'] = self.s_오늘
        df_종목별잔고['조회시간'] = pd.Timestamp.now().strftime('%H:%M:%S')

        # 종목별잔고 저장 - 보유기간 관리를 위해 15:30:00 이전꺼만 저장
        if pd.Timestamp.now() < pd.Timestamp('15:30:00'):
            df_종목별잔고.to_csv(os.path.join(self.folder_종목잔고, f'df_종목별잔고_{self.s_오늘}.csv'),
                                encoding='cp949', index=False)

        return dic_계좌잔고, df_종목별잔고, dic_종목코드2종목명

    def _check_보유기간(self, li_대상종목):
        """ 입력받은 종목에 대해 보유기간 확인 후 리턴 """
        # 전체일자 확인
        folder_일봉캐시 = os.path.join(self.folder_work.replace('bbTrader', 'spTraderV2'), '데이터', '차트캐시', '일봉1')
        li_전체일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_일봉캐시) if '.pkl' in 파일]
        li_전체일자 = sorted(일자 for 일자 in li_전체일자 if 일자 <= self.s_오늘)
        s_7일전 = min(li_전체일자[-7:]) if len(li_전체일자) > 0 else '0'

        # 종목별잔고 이력 확인
        li_파일일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(self.folder_종목잔고) if '.csv' in 파일]
        li_파일일자 = sorted(일자 for 일자 in li_파일일자 if 일자 >= s_7일전)
        df_잔고이력 = pd.concat([pd.read_csv(os.path.join(self.folder_종목잔고, f'df_종목별잔고_{일자}.csv'),
                                         encoding='cp949', dtype=str) for 일자 in li_파일일자]).sort_values('조회일자')
        df_잔고이력['종목코드'] = df_잔고이력['종목코드'].str.zfill(6)

        # 매수일자, 보유기간 확인
        li_종가매수일, li_보유기간 = list(), list()
        for s_종목코드 in li_대상종목:
            # 종목 잔고이력 확인
            df_잔고이력_종목 = df_잔고이력.loc[df_잔고이력['종목코드'] == s_종목코드].sort_values('조회일자').reset_index(drop=True)

            # 매수일자 확인 - 종가매수 기준
            s_등장일자 = df_잔고이력_종목['조회일자'].values[0] if not df_잔고이력_종목.empty else self.s_오늘
            s_종가매수일 = max(일자 for 일자 in li_전체일자 if 일자 < s_등장일자)
            li_종가매수일.append(s_종가매수일)

            # 보유기간 확인 - 종가매수 기준
            n_보유기간 = len([일자 for 일자 in li_전체일자 if s_종가매수일 < 일자 < self.s_오늘])
            li_보유기간.append(n_보유기간)

        return li_종가매수일, li_보유기간


def run():
    """ 실행 함수 """
    t = TraderBot()
    t.avtivate_종목감시()

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
