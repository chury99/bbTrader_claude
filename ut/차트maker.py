import os
import sys
import json
import time
import re
import multiprocessing as mp

import pandas as pd
import matplotlib.pyplot as plt
from fontTools.varLib.models import nonNone
from pandas.core.methods.selectn import SelectNSeries
from tqdm import tqdm

import ut.로그maker, ut.폴더manager, ut.도구manager as Tool
# import xapi.RestAPI_kiwoom, xapi.WebsocketAPI_kiwoom


# noinspection PyPep8Naming,NonAsciiCharacters,SpellCheckingInspection
def make_캔들차트(ax, df_차트, s_봉구분, s_차트구분, b_legend=True):
    """ df로 입력받은 일봉 데이터로 차트 생성하여 리턴 """
    # 기준정보 정의
    dic_색상 = dict(파랑='C0', 주황='C1', 녹색='C2', 빨강='C3', 보라='C4', 고동='C5', 분홍='C6', 회색='C7', 풀색='C8', 하늘='C9')
    df_차트 = df_차트.sort_values('일자') if '일봉' in s_봉구분 else\
            df_차트.sort_values(['일자', '시간']) if '분봉' in s_봉구분 else\
            df_차트.reset_index(drop=True).sort_values(['체결시간']) if '초봉' in s_봉구분 else None

    # 그래프용 데이터 정의
    li_일시 = [f'{일자[4:6]}-{일자[6:8]}' for 일자 in df_차트['일자']] if '일봉' in s_봉구분 else\
            [시간[:5] for 시간 in df_차트['시간']] if '분봉' in s_봉구분 else\
            [시간 for 시간 in df_차트['체결시간']] if '초봉' in s_봉구분 else None
    ary_시가 = df_차트['시가'].values
    ary_고가 = df_차트['고가'].values
    ary_저가 = df_차트['저가'].values
    ary_종가 = df_차트['종가'].values
    ary_거래량 = df_차트['거래량'].values
    ary_바디 = (df_차트['종가'] - df_차트['시가']).replace(0, 0.5).values
    li_색상_캔들 = [dic_색상['파랑'] if 바디 < 0 else dic_색상['빨강'] for 바디 in ary_바디]
    li_색상_거래량 = [dic_색상['파랑'] if 거래량차이 < 0 else dic_색상['빨강'] for 거래량차이 in (df_차트['거래량'] - df_차트['거래량'].shift(1))]
    ary_종가ma5 = df_차트['종가ma5'].values
    ary_종가ma10 = df_차트['종가ma10'].values
    ary_종가ma20 = df_차트['종가ma20'].values
    ary_종가ma60 = df_차트['종가ma60'].values
    ary_종가ma120 = df_차트['종가ma120'].values
    ary_거래량ma5 = df_차트['거래량ma5'].values
    ary_거래량ma20 = df_차트['거래량ma20'].values
    ary_거래량ma60 = df_차트['거래량ma60'].values
    ary_거래량ma120 = df_차트['거래량ma120'].values

    # 그래프 설정
    if s_차트구분 == '캔들':
        ax.bar(li_일시, height=ary_바디, bottom=ary_시가, width=0.8, color=li_색상_캔들)
        ax.vlines(li_일시, ary_저가, ary_고가, lw=0.5, color=li_색상_캔들)
        ax.plot(li_일시, ary_종가ma5, lw=0.5, color=dic_색상['분홍'], label='ma5')
        ax.plot(li_일시, ary_종가ma10, lw=0.5, color=dic_색상['파랑'], label='ma10')
        ax.plot(li_일시, ary_종가ma20, lw=2, color=dic_색상['주황'], label='ma20', alpha=0.5)
        ax.plot(li_일시, ary_종가ma60, lw=0.5, color=dic_색상['녹색'], label='ma60')
        ax.plot(li_일시, ary_종가ma120, lw=2, color='black', label='ma120', alpha=0.5)

        # 스케일 설정
        li_대상컬럼 = ['저가', '고가', '종가ma5', '종가ma10', '종가ma20', '종가ma60', '종가ma120']
        n_최소값 = df_차트.loc[:, li_대상컬럼].min().min()
        n_최대값 = df_차트.loc[:, li_대상컬럼].max().max()
        ax.set_ylim(n_최소값 * 0.98, n_최대값 * 1.02)

    if s_차트구분 == '거래량':
        ax.bar(li_일시, ary_거래량, width=0.8, color=li_색상_거래량)
        ax.plot(li_일시, ary_거래량ma5, lw=0.5, color=dic_색상['분홍'], label='ma5')
        ax.plot(li_일시, ary_거래량ma20, lw=2, color=dic_색상['주황'], label='ma20', alpha=0.5)
        ax.plot(li_일시, ary_거래량ma60, lw=0.5, color=dic_색상['녹색'], label='ma60')
        ax.plot(li_일시, ary_거래량ma120, lw=0.5, color='black', label='ma120')

    # 뷰 설정
    ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    # if b_legend:
    #     ax.legend(loc='upper left', fontsize=8)
    ret = ax.legend(loc='upper left', fontsize=8) if b_legend else None

    return li_일시


# noinspection PyPep8Naming,NonAsciiCharacters,SpellCheckingInspection
class ChartMaker:
    def __init__(self):
        # 그래프 한글 설정
        from matplotlib import font_manager
        path_font = 'c:/Windows/Fonts/malgun.ttf' if os.name == 'nt' else\
                    '/System/Library/Fonts/Supplemental/AppleGothic.ttf' if os.name == 'posix' else None
        font_name = font_manager.FontProperties(fname=path_font).get_name()
        plt.rcParams['font.family'] = font_name
        plt.rcParams['axes.unicode_minus'] = False

        # 차트 색상코드 정의 - 기본색상코드
        self.dic_색상 = dict(파랑='C0', 주황='C1', 녹색='C2', 빨강='C3', 보라='C4',
                           고동='C5', 분홍='C6', 회색='C7', 올리브='C8', 하늘='C9')

    def _make_초봉차트(self, ax, dic_매개변수):
        """ 초봉 데이터 기준 주가변화 차트 생성 후 ax 리턴 """
        # 기준정보 정의
        s_일자 = dic_매개변수['s_일자']
        s_종목코드 = dic_매개변수['s_종목코드']
        s_종목명 = dic_매개변수['s_종목명']
        df_초봉 = dic_매개변수['df_초봉']
        n_봉수 = dic_매개변수['n_봉수']

        # 스케일 정보 정의
        n_시세_max = df_초봉['고가'].max()
        n_시세_min = df_초봉['저가'].min()
        # n_거래량_max = max(df_초봉['매수량'].max(), df_초봉['매도량'].max())
        # n_거래량_min = min(df_초봉['매수량'].min(), df_초봉['매도량'].min())
        # n_거래횟수_max = max(df_초봉['매수횟수'].max(), df_초봉['매도횟수'].max(), df_초봉['체결횟수'].max())
        # n_거래횟수_min = min(df_초봉['매수횟수'].min(), df_초봉['매도횟수'].min(), df_초봉['체결횟수'].min())

        # ax 생성
        s_차트명 = f'[ {s_종목명}({s_종목코드}) ] {n_봉수}초봉'
        ax.set_title(s_차트명, loc='left', fontsize=10, fontweight='bold')
        ax.vlines(df_초봉.index, df_초봉['저가'], df_초봉['고가'], lw=0.5, color='black')
        # ax_거래량 = ax.twinx()
        # ax_거래량.plot(df_초봉.index, df_초봉['매수량'], lw=0.5, alpha=0.7, color=self.dic_색상['빨강'])
        # ax_거래량.plot(df_초봉.index, df_초봉['매도량'], lw=0.5, alpha=0.7, color=self.dic_색상['파랑'])
        # ax_체결횟수 = ax.twinx()
        # ax_체결횟수.plot(df_초봉.index, df_초봉['매수횟수'], lw=1, alpha=0.2, color=self.dic_색상['빨강'])
        # ax_체결횟수.plot(df_초봉.index, df_초봉['매도횟수'], lw=1, alpha=0.2, color=self.dic_색상['파랑'])
        # ax_체결횟수.plot(df_초봉.index, df_초봉['체결횟수'], lw=1, alpha=0.3, color='black')

        # 스케일 설정
        # ax.set_ylim(n_시세_min * 0.9, n_시세_max * 1.1)
        ax.set_ylim(n_시세_min, n_시세_max)
        ax.set_yticks([])
        # ax_거래량.set_ylim(n_거래량_min * 0.9, n_거래량_max * 1.1)
        # ax_거래량.set_yticks([])
        # ax_체결횟수.set_ylim(n_거래횟수_min * 0.9, n_거래횟수_max * 1.1)
        # ax_체결횟수.set_yticks([])

        return ax

    def make_수익리포트_ax_매수매도(ax, dic_수익정보):
        """ df_체결잔고 기준으로 주가 변화 및 매수매도 시점 표기 후 ax 리턴 """
        # 기준정보 정의
        s_일자 = dic_수익정보['s_일자']
        s_종목코드 = dic_수익정보['s_종목코드']
        s_종목명 = dic_수익정보['s_종목명']
        n_거래순번 = dic_수익정보['n_거래순번']
        df_초봉 = dic_수익정보['df_초봉']
        df_거래정보_종목 = dic_수익정보['df_거래정보_종목']

        # 매수매도 정보 정의
        dt_매수시점 = pd.Timestamp(f'{s_일자} {df_거래정보_종목["매수시간"].values[n_거래순번]}')
        dt_매도시점 = pd.Timestamp(f'{s_일자} {df_거래정보_종목["매도시간"].values[n_거래순번]}')
        dt_타임아웃 = dt_매수시점 + pd.Timedelta(minutes=5)
        n_매수가 = df_거래정보_종목['매수가'].values[n_거래순번]
        n_매도가 = df_거래정보_종목['매도가'].values[n_거래순번]
        s_매도사유 = df_거래정보_종목['매도사유'].values[n_거래순번]
        n_초봉 = df_거래정보_종목['초봉'].values[n_거래순번]
        s_선정사유 = df_거래정보_종목['선정사유'].values[n_거래순번]
        s_거래구분 = df_거래정보_종목['거래구분'].values[n_거래순번]
        n_수익률 = (n_매도가 / n_매수가 - 1) * 100 - 0.2 if n_매수가 is not None else 0

        # 차트 정보 정의
        df_초봉_차트 = df_초봉[df_초봉.index >= dt_매수시점 - pd.Timedelta(minutes=2)]
        df_초봉_차트 = df_초봉_차트[df_초봉_차트.index <= dt_매수시점 + pd.Timedelta(minutes=8)]

        # 스케일 정보 정의
        n_시세_max = df_초봉['고가'].max()
        n_시세_min = df_초봉['저가'].min()
        n_거래량_max = max(df_초봉['매수량'].max(), df_초봉['매도량'].max())
        n_거래량_min = min(df_초봉['매수량'].min(), df_초봉['매도량'].min())
        n_거래횟수_max = max(df_초봉['매수횟수'].max(), df_초봉['매도횟수'].max(), df_초봉['체결횟수'].max())
        n_거래횟수_min = min(df_초봉['매수횟수'].min(), df_초봉['매도횟수'].min(), df_초봉['체결횟수'].min())

        # 기본색상코드 정의
        dic_색상 = {'파랑': 'C0', '주황': 'C1', '녹색': 'C2', '빨강': 'C3', '보라': 'C4',
                  '고동': 'C5', '분홍': 'C6', '회색': 'C7', '올리브': 'C8', '하늘': 'C9'}

        # ax 생성
        s_차트명 = f'[ {s_종목명}({s_종목코드}) ] {n_초봉}초봉' if n_거래순번 == 0 else ''
        ax.set_title(s_차트명, loc='left', fontsize=10, fontweight='bold')
        ax.vlines(df_초봉_차트.index, df_초봉_차트['저가'], df_초봉_차트['고가'], lw=0.5, color='black')
        ax_거래량 = ax.twinx()
        ax_거래량.plot(df_초봉_차트.index, df_초봉_차트['매수량'], lw=0.5, alpha=0.7, color=dic_색상['빨강'])
        ax_거래량.plot(df_초봉_차트.index, df_초봉_차트['매도량'], lw=0.5, alpha=0.7, color=dic_색상['파랑'])
        ax_체결횟수 = ax.twinx()
        ax_체결횟수.plot(df_초봉_차트.index, df_초봉_차트['매수횟수'], lw=1, alpha=0.2, color=dic_색상['빨강'])
        ax_체결횟수.plot(df_초봉_차트.index, df_초봉_차트['매도횟수'], lw=1, alpha=0.2, color=dic_색상['파랑'])
        ax_체결횟수.plot(df_초봉_차트.index, df_초봉_차트['체결횟수'], lw=1, alpha=0.3, color='black')

        # 매수매도 시점 표기
        ax.axvline(dt_매수시점, lw=1, alpha=0.5, color=dic_색상['녹색']) if dt_매수시점 is not None else None
        ax.axvline(dt_매도시점, lw=1, alpha=0.5, color=dic_색상['보라']) if dt_매도시점 is not None else None
        ax.axhline(n_매수가, lw=1, alpha=0.5, color=dic_색상['녹색']) if n_매수가 is not None else None
        ax.axhline(n_매도가, lw=1, alpha=0.5, color=dic_색상['보라']) if n_매도가 is not None else None
        ax.axvspan(df_초봉_차트.index[0], dt_매수시점, alpha=0.3, color=dic_색상['회색']) if dt_매수시점 is not None else None
        ax.axvspan(dt_타임아웃, df_초봉_차트.index[-1], alpha=0.3, color=dic_색상['회색']) if dt_타임아웃 is not None else None

        # 스케일 설정
        ax.set_ylim(n_시세_min * 0.9, n_시세_max * 1.1)
        ax.set_yticks([])
        ax.set_xticks([dt_매수시점],
                      labels=[
                          f'{s_거래구분}|{s_선정사유}-{dt_매수시점.strftime("%H:%M:%S")}-{n_매수가:,.0f}-{s_매도사유}|{n_수익률:.1f}%'],
                      ha='center')
        ax_거래량.set_ylim(n_거래량_min, n_거래량_max * 1.1)
        ax_거래량.set_yticks([])
        ax_체결횟수.set_ylim(0, n_거래횟수_max * 1.1)
        ax_체결횟수.set_yticks([])

        return ax

        pass



def find_전일종가(df_ohlcv):
    """ 입력 받은 일봉 또는 분봉에 해당 종목의 전일 종가 생성 후 df 리턴 """
    # 전일종가 존재 시 리턴
    li_생성 = ['전일종가', '전일대비(%)']
    li_존재 = [1 if 컬럼 in df_ohlcv.columns else 0 for 컬럼 in li_생성]
    if 0 not in li_존재:
        return df_ohlcv

    # 폴더 정의
    import UT_폴더manager
    folder_캐시변환 = UT_폴더manager.dic_폴더정보['데이터|캐시변환']

    # 대상일 확인
    li_전체일 = [re.findall(r'\d{8}', 파일명)[0] for 파일명 in os.listdir(folder_캐시변환)
              if 'dic_코드별_분봉_' in 파일명 and '.pkl' in 파일명]
    ary_기준일 = df_ohlcv['일자'].unique()
    s_추가일 = max([일자 for 일자 in li_전체일 if 일자 < ary_기준일.min()])
    li_대상일 = [s_추가일] + list(ary_기준일)

    # 일봉 불러오기
    s_종목코드 = df_ohlcv['종목코드'].values[0]
    li_대상월 = list(pd.Series(li_대상일).apply(lambda x: x[:6]).unique())
    li_df_일봉 = [pd.read_pickle(os.path.join(folder_캐시변환, f'dic_코드별_일봉_{s_해당월}.pkl'))[s_종목코드]
                for s_해당월 in li_대상월]
    df_일봉 = pd.concat(li_df_일봉, axis=0).sort_values('일자').reset_index(drop=True)
    dic_일자2전일종가 = df_일봉.set_index('일자').to_dict()['전일종가']
    n_전일종가_마지막 = df_일봉['종가'].values[-1]

    # df_전일종가 인덱스 설정
    df_전일종가 = df_ohlcv.copy()
    if '시간' in df_전일종가.columns:
        df_전일종가['일자시간'] = df_전일종가['일자'] + ' ' + df_전일종가['시간']
        df_전일종가['일자시간'] = pd.to_datetime(df_전일종가['일자시간'], format='%Y%m%d %H:%M:%S')
        df_전일종가 = df_전일종가.set_index(keys='일자시간').sort_index(ascending=True)
    else:
        df_전일종가 = df_전일종가.sort_values('일자')

    # df 전일종가 데이터 생성
    df_전일종가['전일종가'] = df_전일종가['일자'].apply(lambda x:
                                          dic_일자2전일종가[x] if x in dic_일자2전일종가.keys() else n_전일종가_마지막)
    df_전일종가['전일대비(%)'] = (df_전일종가['종가'] / df_전일종가['전일종가'] - 1) * 100

    return df_전일종가


def make_이동평균(df_ohlcv):
    """ 입력 받은 일봉 또는 분봉에 각종 이동평균 데이터 생성 후 df 리턴 """
    # 이동평균 존재 시 리턴
    li_생성 = ['종가ma5', '종가ma10', '종가ma20', '종가ma60', '종가ma120',
             '거래량ma5', '거래량ma20', '거래량ma60', '거래량ma120']
    li_존재 = [1 if 컬럼 in df_ohlcv.columns else 0 for 컬럼 in li_생성]
    if 0 not in li_존재:
        return df_ohlcv

    # df_이동평균 인덱스 설정
    df_이동평균 = df_ohlcv.copy()
    s_구분 = '분봉' if '시간' in df_ohlcv.columns else '일봉'
    if s_구분 == '분봉':
        df_이동평균['일자시간'] = df_이동평균['일자'] + ' ' + df_이동평균['시간']
        df_이동평균['일자시간'] = pd.to_datetime(df_이동평균['일자시간'], format='%Y%m%d %H:%M:%S')
        df_이동평균 = df_이동평균.set_index(keys='일자시간').sort_index(ascending=True)
    else:
        df_이동평균 = df_이동평균.sort_values('일자')

    # df_이동평균 인덱스 설정
    df_이동평균['종가ma5'] = df_이동평균['종가'].rolling(5).mean()
    df_이동평균['종가ma10'] = df_이동평균['종가'].rolling(10).mean()
    df_이동평균['종가ma20'] = df_이동평균['종가'].rolling(20).mean()
    df_이동평균['종가ma60'] = df_이동평균['종가'].rolling(60).mean()
    df_이동평균['종가ma120'] = df_이동평균['종가'].rolling(120).mean()
    df_이동평균['거래량ma5'] = df_이동평균['거래량'].rolling(5).mean()
    df_이동평균['거래량ma20'] = df_이동평균['거래량'].rolling(20).mean()
    df_이동평균['거래량ma60'] = df_이동평균['거래량'].rolling(60).mean()
    df_이동평균['거래량ma120'] = df_이동평균['거래량'].rolling(120).mean()

    return df_이동평균


# noinspection PyPep8Naming,PyTypeChecker
def make_차트(df_ohlcv, n_봉수=None):
    """ 입력 받은 일봉 또는 분봉 기준으로 차트 생성 후 fig 리턴 """
    # 기본색상코드 정의
    dic_색상 = {'파랑': 'C0', '주황': 'C1', '녹색': 'C2', '빨강': 'C3', '보라': 'C4',
              '고동': 'C5', '분홍': 'C6', '회색': 'C7', '올리브': 'C8', '하늘': 'C9'}

    # 데이터 정렬
    s_구분 = '분봉' if '시간' in df_ohlcv.columns else '일봉'
    if s_구분 == '분봉':
        df_ohlcv['일시'] = df_ohlcv['일자'].apply(lambda x: f'{x[:4]}-{x[4:6]}-{x[6:]}') + ' ' + df_ohlcv['시간']
        df_ohlcv = df_ohlcv.sort_values('일시')
    else:
        df_ohlcv = df_ohlcv.sort_values('일자')

    # 데이터 잘라내기
    if n_봉수 is not None:
        df_ohlcv = df_ohlcv[-1 * n_봉수:]

    # 차트 정보 생성
    s_종목코드 = df_ohlcv['종목코드'].values[0]
    s_종목명 = df_ohlcv['종목명'].values[0]
    n_봉구분 = int((pd.Timestamp(df_ohlcv['일시'].values[1]) - pd.Timestamp(df_ohlcv['일시'].values[0])).seconds / 60)\
            if s_구분 == '분봉' else None
    s_봉구분 = f'{n_봉구분}분봉' if s_구분 == '분봉' else '일봉'

    # 추가 데이터 생성
    ary_x = df_ohlcv['일시'].values if s_구분 == '분봉' else df_ohlcv['일자'].values
    df_ohlcv['몸통'] = (df_ohlcv['종가'] - df_ohlcv['시가']).apply(lambda x: x if x != 0 else 0.1)
    li_색상_캔들 = df_ohlcv['몸통'].apply(lambda x: dic_색상['파랑'] if x < 0 else dic_색상['빨강'])
    li_색상_거래량 = (df_ohlcv['거래량'] - df_ohlcv['거래량'].shift(1)).apply(lambda x:
                                                                   dic_색상['파랑'] if x < 0 else dic_색상['빨강'])

    # 차트 레이아웃 설정
    fig = plt.Figure(figsize=(16, 9), tight_layout=True)
    fig.suptitle(f'[{s_봉구분}] {s_종목명}({s_종목코드})', fontsize=16)
    ax_캔들 = fig.add_subplot(3, 1, (1, 2))
    ax_거래량 = fig.add_subplot(3, 1, 3)

    # 캔들 차트 생성
    ax_캔들.bar(ary_x, height=df_ohlcv['몸통'], bottom=df_ohlcv['시가'], width=0.8, color=li_색상_캔들)
    ax_캔들.vlines(ary_x, df_ohlcv['저가'], df_ohlcv['고가'], lw=0.5, color=li_색상_캔들)
    ax_캔들.plot(ary_x, df_ohlcv['종가ma5'], lw=0.5, color=dic_색상['분홍'], label='ma5')
    ax_캔들.plot(ary_x, df_ohlcv['종가ma10'], lw=0.5, color=dic_색상['파랑'], label='ma10')
    ax_캔들.plot(ary_x, df_ohlcv['종가ma20'], lw=2, color=dic_색상['주황'], label='ma20', alpha=0.5)
    ax_캔들.plot(ary_x, df_ohlcv['종가ma60'], lw=0.5, color=dic_색상['녹색'], label='ma60')
    ax_캔들.plot(ary_x, df_ohlcv['종가ma120'], lw=2, color='black', label='ma120', alpha=0.5)
    ax_캔들.set_ylim(df_ohlcv['저가'].min() * 0.98, df_ohlcv['고가'].max() * 1.02)

    # 거래량 차트 생성
    ax_거래량.bar(ary_x, df_ohlcv['거래량'], width=0.8, color=li_색상_거래량)
    ax_거래량.plot(ary_x, df_ohlcv['거래량ma5'], lw=0.5, color=dic_색상['분홍'], label='ma5')
    ax_거래량.plot(ary_x, df_ohlcv['거래량ma20'], lw=2, color=dic_색상['주황'], label='ma20', alpha=0.5)
    ax_거래량.plot(ary_x, df_ohlcv['거래량ma60'], lw=0.5, color=dic_색상['녹색'], label='ma60')
    ax_거래량.plot(ary_x, df_ohlcv['거래량ma120'], lw=0.5, color='black', label='ma120')

    # 공통 설정
    for ax in fig.axes:
        df_틱 = df_ohlcv.copy().reset_index()
        if s_구분 == '분봉':
            df_틱['라벨'] = df_틱['일자'].apply(lambda x: f'{x[4:6]}-{x[6:8]}')
        else:
            df_틱['라벨'] = df_틱['일자'].apply(lambda x: f'{x[2:4]}-{x[4:6]}')
        df_틱['변화'] = df_틱['라벨'] == df_틱['라벨'].shift(1)
        df_틱 = df_틱[df_틱['변화'] == False]
        ax.set_xticks(df_틱.index, labels=df_틱['라벨'])
        ax.grid(linestyle='--', alpha=0.5)
        ax.legend(loc='upper left', fontsize=8)

    return fig


def make_수익리포트(df_거래정보, dic_매매정보, li_컬럼명_강조):
    """ 수익요약 데이터 기준으로 리포트 생성하여 리턴 """
    # 기준정보 정의
    s_일자 = dic_매매정보['s_일자']
    n_초봉 = dic_매매정보['n_초봉']
    df_수익요약 = dic_매매정보['df_수익요약']
    folder_캐시변환 = dic_매매정보['folder_캐시변환']

    # 초봉 읽어오기
    dic_초봉 = pd.read_pickle(os.path.join(folder_캐시변환, f'dic_코드별_{n_초봉}초봉_{s_일자}.pkl'))

    # 리포트 데이터 정의
    li_종목코드 = [종목코드 for 종목코드 in df_거래정보['종목코드'].unique() if 종목코드 is not None]
    dic_종목코드2종목명 = df_거래정보.set_index('종목코드')['종목명'].to_dict()
    n_테이블_세로 = 4
    n_차트_가로 = 4
    li_차트_세로 = [(len(df_거래정보[df_거래정보['종목코드'] == 종목코드])
                    + (n_차트_가로 - 1)) // n_차트_가로 for 종목코드 in li_종목코드]
    n_차트_세로 = n_테이블_세로 + sum(li_차트_세로)
    fig = plt.Figure(figsize=(16, n_차트_세로 * 2), tight_layout=False)

    # 리포트 생성 - 수익요약
    ax_수익요약 = fig.add_subplot(n_차트_세로, n_차트_가로, (1, n_테이블_세로 * n_차트_가로))
    ax_수익요약 = make_수익리포트_ax_수익요약(ax=ax_수익요약, df_수익요약=df_수익요약, li_컬럼명_강조=li_컬럼명_강조)

    # 리포트 생성 - 매수매도
    li_종목별줄수 = list()
    for i_종목순번, s_종목코드 in enumerate(li_종목코드):
        # 그래프용 데이터 생성
        df_초봉 = dic_초봉[s_종목코드]
        s_종목명 = dic_종목코드2종목명[s_종목코드]
        dic_매매정보['s_종목코드'] = s_종목코드
        dic_매매정보['s_종목명'] = s_종목명
        dic_매매정보['df_초봉'] = df_초봉
        dic_매매정보['df_거래정보_종목'] = df_거래정보[df_거래정보['종목코드'] == s_종목코드]

        # 매수매도 그래프 설정
        n_거래수_종목 = len(df_거래정보[df_거래정보['종목코드'] == s_종목코드])
        for i_거래순번 in range(n_거래수_종목):
            # 위치 설정
            dic_매매정보['n_거래순번'] = i_거래순번
            n_종목줄수 = sum(li_종목별줄수)
            n_차트위치 = (n_테이블_세로 * n_차트_가로) + (n_종목줄수 * n_차트_가로) + i_거래순번 + 1

            # 차트 생성
            ax_매수매도 = fig.add_subplot(n_차트_세로, n_차트_가로, n_차트위치)
            ax_매수매도 = make_수익리포트_ax_매수매도(ax=ax_매수매도, dic_수익정보=dic_매매정보)

            # 위치 카운트용 정보 업데이트
            if i_거래순번 + 1 == n_거래수_종목:
                li_종목별줄수.append((n_거래수_종목 + (n_차트_가로 - 1)) // n_차트_가로)

    return fig


def make_수익리포트_ax_수익요약(ax, df_수익요약, li_컬럼명_강조=None):
    """ df_수익요약 기준으로 리포트 테이블 변환 후 ax 리턴 """
    # df_리포트 생성
    df_리포트 = pd.DataFrame()
    df_리포트['일자'] = df_수익요약['일자']
    li_컬럼명 = [컬럼명 for 컬럼명 in df_수익요약.columns if '일자' not in 컬럼명]
    for s_컬럼명 in li_컬럼명:
        df_리포트[s_컬럼명] = df_수익요약[s_컬럼명].apply(lambda x: f'{x:.1f}' if x is not None else x)

    # ax 생성
    ax.set_title('[ 수익요약 ]', loc='center', fontsize=10, fontweight='bold')
    ax.axis('tight')
    ax.axis('off')
    obj_테이블 = ax.table(cellText=df_리포트.values, colLabels=df_리포트.columns, cellLoc='center', loc='center')
    obj_테이블.set_fontsize(8)
    obj_테이블.scale(1.0, 1.6)

    # 선정 조건에 배경색 표기 - 회색
    try:
        for n_col in range(len(df_수익요약.columns)):
            obj_테이블[2, n_col].set_facecolor('lightgrey')
        # n_max위치 = df_수익요약.set_index('일자').T['10성능%'].argmax() + 1
        # for n_row in range(len(df_수익요약) + 1):
        #     obj_테이블[n_row, n_max위치].set_facecolor('yellow')
        # obj_테이블[0, n_max위치].set_text_props(fontweight='bold')
        # obj_테이블[2, n_max위치].set_text_props(fontweight='bold')
    except TypeError:
        pass

    # 강조할 컬럼 표기 - 노란색
    li_컬럼명 = list(df_수익요약.columns)
    if li_컬럼명_강조 is None:
        # li_컬럼명_강조 = [li_컬럼명[df_수익요약.set_index('일자').T['10성능%'].argmax()]]
        li_컬럼명_일자제외 = [컬럼명 for 컬럼명 in li_컬럼명 if '일자' not in 컬럼명]
        # df_수익요약.loc[:, li_컬럼명_일자제외] = df_수익요약.loc[:, li_컬럼명_일자제외].astype(float)
        for s_컬럼명 in li_컬럼명_일자제외:
            df_수익요약[s_컬럼명] = df_수익요약[s_컬럼명].astype(float)
        li_컬럼명_강조 = list(df_수익요약.loc[df_수익요약['일자'] == '10성능%', li_컬럼명_일자제외].T.idxmax())
        # li_컬럼명_강조 = [df_수익요약[df_수익요약['일자'] == '10성능%'].iloc[0].idxmax()]
    for s_컬럼명 in li_컬럼명_강조:
        n_컬럼_강조 = li_컬럼명.index(s_컬럼명)
        for n_row in range(len(df_수익요약) + 1):
            obj_테이블[n_row, n_컬럼_강조].set_facecolor('yellow')
        obj_테이블[0, n_컬럼_강조].set_text_props(fontweight='bold')
        obj_테이블[2, n_컬럼_강조].set_text_props(fontweight='bold')

    return ax


def make_수익리포트_ax_매수매도(ax, dic_수익정보):
    """ df_체결잔고 기준으로 주가 변화 및 매수매도 시점 표기 후 ax 리턴 """
    # 기준정보 정의
    s_일자 = dic_수익정보['s_일자']
    s_종목코드 = dic_수익정보['s_종목코드']
    s_종목명 = dic_수익정보['s_종목명']
    n_거래순번 = dic_수익정보['n_거래순번']
    df_초봉 = dic_수익정보['df_초봉']
    df_거래정보_종목 = dic_수익정보['df_거래정보_종목']

    # 매수매도 정보 정의
    dt_매수시점 = pd.Timestamp(f'{s_일자} {df_거래정보_종목["매수시간"].values[n_거래순번]}')
    dt_매도시점 = pd.Timestamp(f'{s_일자} {df_거래정보_종목["매도시간"].values[n_거래순번]}')
    dt_타임아웃 = dt_매수시점 + pd.Timedelta(minutes=5)
    n_매수가 = df_거래정보_종목['매수가'].values[n_거래순번]
    n_매도가 = df_거래정보_종목['매도가'].values[n_거래순번]
    s_매도사유 = df_거래정보_종목['매도사유'].values[n_거래순번]
    n_초봉 = df_거래정보_종목['초봉'].values[n_거래순번]
    s_선정사유 = df_거래정보_종목['선정사유'].values[n_거래순번]
    s_거래구분 = df_거래정보_종목['거래구분'].values[n_거래순번]
    n_수익률 = (n_매도가 / n_매수가 - 1) * 100 - 0.2 if n_매수가 is not None else 0

    # 차트 정보 정의
    df_초봉_차트 = df_초봉[df_초봉.index >= dt_매수시점 - pd.Timedelta(minutes=2)]
    df_초봉_차트 = df_초봉_차트[df_초봉_차트.index <= dt_매수시점 + pd.Timedelta(minutes=8)]

    # 스케일 정보 정의
    n_시세_max = df_초봉['고가'].max()
    n_시세_min = df_초봉['저가'].min()
    n_거래량_max = max(df_초봉['매수량'].max(), df_초봉['매도량'].max())
    n_거래량_min = min(df_초봉['매수량'].min(), df_초봉['매도량'].min())
    n_거래횟수_max = max(df_초봉['매수횟수'].max(), df_초봉['매도횟수'].max(), df_초봉['체결횟수'].max())
    n_거래횟수_min = min(df_초봉['매수횟수'].min(), df_초봉['매도횟수'].min(), df_초봉['체결횟수'].min())

    # 기본색상코드 정의
    dic_색상 = {'파랑': 'C0', '주황': 'C1', '녹색': 'C2', '빨강': 'C3', '보라': 'C4',
              '고동': 'C5', '분홍': 'C6', '회색': 'C7', '올리브': 'C8', '하늘': 'C9'}

    # ax 생성
    s_차트명 = f'[ {s_종목명}({s_종목코드}) ] {n_초봉}초봉' if n_거래순번 == 0 else ''
    ax.set_title(s_차트명, loc='left', fontsize=10, fontweight='bold')
    ax.vlines(df_초봉_차트.index, df_초봉_차트['저가'], df_초봉_차트['고가'], lw=0.5, color='black')
    ax_거래량 = ax.twinx()
    ax_거래량.plot(df_초봉_차트.index, df_초봉_차트['매수량'], lw=0.5, alpha=0.7, color=dic_색상['빨강'])
    ax_거래량.plot(df_초봉_차트.index, df_초봉_차트['매도량'], lw=0.5, alpha=0.7, color=dic_색상['파랑'])
    ax_체결횟수 = ax.twinx()
    ax_체결횟수.plot(df_초봉_차트.index, df_초봉_차트['매수횟수'], lw=1, alpha=0.2, color=dic_색상['빨강'])
    ax_체결횟수.plot(df_초봉_차트.index, df_초봉_차트['매도횟수'], lw=1, alpha=0.2, color=dic_색상['파랑'])
    ax_체결횟수.plot(df_초봉_차트.index, df_초봉_차트['체결횟수'], lw=1, alpha=0.3, color='black')

    # 매수매도 시점 표기
    ax.axvline(dt_매수시점, lw=1, alpha=0.5, color=dic_색상['녹색']) if dt_매수시점 is not None else None
    ax.axvline(dt_매도시점, lw=1, alpha=0.5, color=dic_색상['보라']) if dt_매도시점 is not None else None
    ax.axhline(n_매수가, lw=1, alpha=0.5, color=dic_색상['녹색']) if n_매수가 is not None else None
    ax.axhline(n_매도가, lw=1, alpha=0.5, color=dic_색상['보라']) if n_매도가 is not None else None
    ax.axvspan(df_초봉_차트.index[0], dt_매수시점, alpha=0.3, color=dic_색상['회색']) if dt_매수시점 is not None else None
    ax.axvspan(dt_타임아웃, df_초봉_차트.index[-1], alpha=0.3, color=dic_색상['회색']) if dt_타임아웃 is not None else None

    # 스케일 설정
    ax.set_ylim(n_시세_min * 0.9, n_시세_max * 1.1)
    ax.set_yticks([])
    ax.set_xticks([dt_매수시점],
                    labels=[f'{s_거래구분}|{s_선정사유}-{dt_매수시점.strftime("%H:%M:%S")}-{n_매수가:,.0f}-{s_매도사유}|{n_수익률:.1f}%'],
                    ha='center')
    ax_거래량.set_ylim(n_거래량_min, n_거래량_max * 1.1)
    ax_거래량.set_yticks([])
    ax_체결횟수.set_ylim(0, n_거래횟수_max * 1.1)
    ax_체결횟수.set_yticks([])

    return ax


if __name__ == "__main__":
    c = ChartMaker()
    pass
