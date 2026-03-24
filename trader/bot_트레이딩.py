import os
import sys
# import json
import time
# import re

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
        self.folder_종목잔고 = dic_폴더정보['매수매도|종목잔고']
        self.folder_신호탐색 = dic_폴더정보['매수매도|신호탐색']
        os.makedirs(self.folder_종목잔고, exist_ok=True)
        os.makedirs(self.folder_신호탐색, exist_ok=True)

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.s_종료시각 = dic_config['종료시각']
        self.n_tr딜레이 = 0.2
        self.n_손절수익률 = 3
        self.n_익절수익률 = self.n_손절수익률 * 3

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호='53977788')
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

        # 로그 기록
        self.make_로그(f'구동 시작')

    def avtivate_종목감시(self):
        """ 보유종목 기준으로 3분봉 감시 """
        # 신호 초기화
        b_탐색신호 = False
        b_매도신호 = False
        s_탐색시점 = '00:00:00'
        df_매도신호 = pd.DataFrame()
        li_매도종목 = list()

        # 감시 루프 생성
        while True:
            # 탐색신호 확인
            dt_현재 = pd.Timestamp.now()
            if not b_탐색신호 and dt_현재.minute % 3 == 0 and dt_현재.second == 1:
            # if not b_탐색신호 and dt_현재.minute % 1 == 0 and dt_현재.second == 1:
                if dt_현재.strftime('%H:%M:%S') != s_탐색시점:
                    b_탐색신호 = True
                    s_탐색시점 = dt_현재.strftime('%H:%M:%S')

            # 신호 탐색
            if b_탐색신호:
            # if True:
                # 매도신호 생성
                df_매도신호 = self.check_매도신호(li_대상종목=self.df_종목별잔고['종목코드'].tolist())
                li_매도종목 = df_매도신호.loc[df_매도신호['매도신호'] == True, '종목코드'].to_list() if not df_매도신호.empty else list()
                b_매도신호 = len(li_매도종목) > 0

                # 매도신호 저장
                if len(df_매도신호) > 0:
                    # 데이터 재정리
                    df_매도신호['일자'] = self.s_오늘
                    df_매도신호['시간'] = s_탐색시점
                    li_컬럼명 = ['일자', '시간'] + [컬럼 for 컬럼 in df_매도신호.columns if 컬럼 not in ['일자', '시간']]
                    df_매도신호 = df_매도신호.loc[:, li_컬럼명]

                    # 데이터 저장
                    path_매도신호 = os.path.join(self.folder_신호탐색, f'df_매도신호_{self.s_오늘}.csv')
                    li_li매도신호 = df_매도신호.values.tolist()
                    li_li매도신호 = [list(df_매도신호.columns)] + li_li매도신호 if not os.path.exists(path_매도신호) else li_li매도신호
                    for li_데이터 in li_li매도신호:
                        li_데이터 = [str(데이터) for 데이터 in li_데이터]
                        with open(path_매도신호, mode='at', encoding='cp949') as f:
                            f.write(f'{','.join(li_데이터)}\n')

                # 로그 기록
                li_매도종목명 = [self.dic_종목코드2종목명.get(종목코드) for 종목코드 in li_매도종목]
                self.make_로그(f'매도신호 탐색\n'
                             f' - 매도대상 {len(li_매도종목명)}건 {li_매도종목명}')

                # 탐색신호 초기화
                b_탐색신호 = False

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
                    n_기준가 = self.df_종목별잔고.loc[s_종목코드, '현재가']
                    s_매도사유 = df_매도신호.loc[s_종목코드, '매도사유']

                    # 매도주문 요청
                    n_주문수량 = n_현재잔고
                    n_주문단가 = self.tool.find_주문단가(n_기준가=n_기준가, n_틱보정=-5)
                    ret = self.api.tr_주식주문(s_구분='매도', s_종목코드=s_종목코드, n_주문수량=n_주문수량, n_주문단가=n_주문단가, s_매매구분='IOC보통')
                    time.sleep(self.n_tr딜레이)

                    # 로그 기록
                    self.make_로그(f'매도주문 완료\n'
                                 f' - {s_매도사유} | {s_종목명}({s_종목코드}) {n_매수가:,.0f} -> {n_주문단가:,.0f}원 {n_주문수량:,.0f}주')

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

    def check_매도신호(self, li_대상종목):
        """ 보유 종목의 매도신호 확인해서 리턴 """
        # 종목별 데이터 확인
        li_dic매도신호 = list()
        for s_종목코드 in li_대상종목:
            # 3분봉 준비
            df_분봉 = self.api.tr_주식분봉차트조회요청(s_종목코드=s_종목코드, s_틱범위='3')
            time.sleep(self.n_tr딜레이)
            df_분봉 = df_분봉.loc[df_분봉['일자'] == self.s_오늘].sort_values('시간')
            df_분봉 = df_분봉.loc[df_분봉['시간'] < pd.Timestamp.now().floor('3min').strftime('%H:%M:%S')]
            if df_분봉.empty: continue

            # 추가지표 생성
            df_분봉['고저'] = df_분봉['고가'] - df_분봉['저가']
            df_분봉['고종가1'] = (df_분봉['고가'] - df_분봉['종가'].shift(1)).abs()
            df_분봉['저종가1'] = (df_분봉['저가'] - df_분봉['종가'].shift(1)).abs()
            df_분봉['ATR'] = df_분봉[['고저', '고종가1', '저종가1']].max(axis=1)
            df_분봉['ATR14'] = df_분봉['ATR'].rolling(14).mean()
            
            # 데이터 생성
            s_종목명 = self.dic_종목코드2종목명[s_종목코드]
            n_매수가 = self.df_종목별잔고.loc[s_종목코드, '매입단가']
            s_시간1 = df_분봉['시간'].values[-1]
            n_시가1 = df_분봉['시가'].values[-1]
            n_종가1 = df_분봉['종가'].values[-1]
            n_비디1 = (n_종가1 - n_시가1) / n_시가1 * 100
            n_당일고가 = df_분봉['고가'].max()
            n_저가3봉 = df_분봉['저가'].values[-4:-1].min() if len(df_분봉) >= 4 else df_분봉['저가'].min()
            n_수익률 = (n_종가1 / n_매수가 - 1) * 100 - 0.2
            n_고가수익률 = (n_당일고가 / n_매수가 - 1) * 100 - 0.2
            n_ATR14 = df_분봉['ATR14'].values[-1] if not pd.isna(df_분봉['ATR14'].values[-1]) else None

            # 매도신호 확인 - 익절
            n_익절기준가 = n_당일고가 - 2 * n_ATR14 if n_ATR14 is not None else 0
            b_고가이탈 = n_종가1 < n_익절기준가 if n_ATR14 is not None else n_종가1 < n_저가3봉
            b_익절 = (n_고가수익률 > self.n_익절수익률) and b_고가이탈 and (n_비디1 < 0)

            # 매도신호 확인 - 손절
            n_손절기준가 = n_매수가 * (100 - self.n_손절수익률 - 0.2) / 100
            b_손절 = (n_종가1 < n_손절기준가) and (s_시간1 > '09:10:00') and (n_비디1 < 0)

            # 결과 정리
            b_매도신호 = b_익절 or b_손절
            s_매도사유 = '익절' if b_익절 else '손절' if b_손절 else '없음'
            dic_매도신호 = dict(종목코드=s_종목코드, 종목명=s_종목명, 매도신호=b_매도신호, 매도사유=s_매도사유, 익절신호=b_익절, 손절신호=b_손절)
            dic_매도신호.update(매수가=n_매수가, 종가1=n_종가1, 수익률=n_수익률,
                            익절기준가=n_익절기준가, 손절기준가=n_손절기준가, 익절수익률=self.n_익절수익률, 손절수익률=self.n_손절수익률,
                            저가3봉=n_저가3봉, 당일고가=n_당일고가, 고가수익률=n_고가수익률, ATR14=n_ATR14)
            li_dic매도신호.append(dic_매도신호)

        # df 정리
        df_매도신호 = pd.DataFrame(li_dic매도신호) if len(li_dic매도신호) > 0 else pd.DataFrame()
        df_매도신호 = df_매도신호.set_index('종목코드', drop=False) if not df_매도신호.empty else df_매도신호

        return df_매도신호

    def _get_종목별잔고(self):
        """ 종목별 잔고 조회하여 df 리턴 """
        # 체결잔고 조회
        dic_계좌잔고, df_종목별잔고 = self.api.tr_체결잔고요청()

        # 데이터 정리
        df_종목별잔고['종목코드'] = df_종목별잔고['종목코드'].str.replace('A', '')
        df_종목별잔고['조회시간'] = pd.Timestamp.now().strftime('%H:%M:%S')
        df_종목별잔고 = df_종목별잔고.set_index('종목코드', drop=False)
        dic_종목코드2종목명 = df_종목별잔고['종목명'].to_dict()

        # 종목별잔고 저장
        df_종목별잔고.to_csv(os.path.join(self.folder_종목잔고, f'df_종목별잔고_{self.s_오늘}.csv'), encoding='cp949', index=False)

        return dic_계좌잔고, df_종목별잔고, dic_종목코드2종목명


def run():
    """ 실행 함수 """
    t = TraderBot()
    t.avtivate_종목감시()

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')
