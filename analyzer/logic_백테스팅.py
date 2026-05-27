import pandas as pd


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def judge_눌림목기본(df_일봉):
    # 기준정보 정의
    dt_당일 = df_일봉.index[-1]
    n_당일시가 = df_일봉.loc[dt_당일, '시가']
    n_당일종가 = df_일봉.loc[dt_당일, '종가']
    n_전일종가 = df_일봉.loc[dt_당일, '전일종가']
    n_당일60 = df_일봉.loc[dt_당일, '종가ma60']
    n_당일120 = df_일봉.loc[dt_당일, '종가ma120']
    n_당일바디 = (n_당일종가 - n_당일시가) / n_전일종가 * 100

    # 선정조건 확인
    b_정배열 = n_당일종가 > n_당일60 > n_당일120
    b_돌파여부 = True in df_일봉['돌파신호'].values[-5:]
    b_눌림여부 = -2 < n_당일바디 < 5

    # 결과 생성
    dic_종목선정 = df_일봉.loc[dt_당일].to_dict()
    dic_종목선정.update(당일종가=n_당일종가, 당일60=n_당일60, 당일120=n_당일120, 당일바디=n_당일바디,
                    종목선정=(b_정배열 and b_돌파여부 and b_눌림여부), 정배열=b_정배열, 돌파여부=b_돌파여부, 눌림여부=b_눌림여부)

    return dic_종목선정


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def judge_눌림목매미(df_일봉):
    # 기준정보 정의
    df_일봉['전일고가3봉'] = df_일봉['고가'].shift(1).rolling(window=3).max()
    df_일봉['돌파신호3봉'] = df_일봉['종가'] > df_일봉['전일고가3봉']
    df_일봉['전일고가14봉'] = df_일봉['고가'].shift(1).rolling(window=14).max()
    df_일봉['돌파신호14봉'] = df_일봉['종가'] > df_일봉['전일고가14봉']
    if len(df_일봉) < 2: return dict()
    dt_당일 = df_일봉.index[-1]
    dt_전일 = df_일봉.index[-2]
    n_당일시가 = df_일봉.loc[dt_당일, '시가']
    n_당일종가 = df_일봉.loc[dt_당일, '종가']
    n_당일60 = df_일봉.loc[dt_당일, '종가ma60']
    n_당일120 = df_일봉.loc[dt_당일, '종가ma120']
    n_전일시가 = df_일봉.loc[dt_전일, '시가']
    n_전일고가 = df_일봉.loc[dt_전일, '고가']
    n_전일종가 = df_일봉.loc[dt_전일, '종가']
    n_전전일종가 = df_일봉.loc[dt_전일, '전일종가']
    n_당일바디율 = (n_당일종가 - n_당일시가) / n_전일종가 * 100
    n_전일바디율 = (n_전일종가 - n_전일시가) / n_전전일종가 * 100
    n_전일바디50 = 0.5 * (n_전일종가 - n_전일시가) + n_전일시가
    n_전일고가14봉 = df_일봉.loc[dt_전일, '전일고가14봉']

    # 선정조건 확인
    b_정배열 = n_당일종가 > n_당일60 > n_당일120
    # b_돌파여부 = True in df_일봉['돌파신호'].values[-5:]
    b_돌파여부 = n_전일종가 > n_전일고가14봉
    b_눌림여부 = -2 < n_당일바디율 < 5
    b_전일돌파 = df_일봉.loc[dt_전일, '돌파신호']
    b_위쪽눌림 = n_전일바디50 < n_당일종가 <= n_전일고가

    # 결과 생성
    dic_종목선정 = df_일봉.loc[dt_당일].to_dict()
    dic_종목선정.update(당일종가=n_당일종가, 당일60=n_당일60, 당일120=n_당일120, 당일바디율=n_당일바디율,
                    전일바디50=n_전일바디50, 전일고가=n_전일고가,
                    종목선정=(b_정배열 and b_돌파여부 and b_눌림여부 and b_전일돌파 and b_위쪽눌림),
                    정배열=b_정배열, 돌파여부=b_돌파여부, 눌림여부=b_눌림여부)

    return dic_종목선정


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def judge_조건확인(df_일봉):
    # 기준정보 정의
    if len(df_일봉) < 2: return dict()
    dt_당일 = df_일봉.index[-1]
    dt_전일 = df_일봉.index[-2]
    n_당일거래대금 = df_일봉.loc[dt_당일, '거래대금(백만)'] / 100
    n_당일종가 = df_일봉.loc[dt_당일, '종가']
    n_전일종가 = df_일봉.loc[dt_당일, '전일종가']
    n_당일종가ma60 = df_일봉.loc[dt_당일, '종가ma60']
    n_당일거래량 = df_일봉.loc[dt_당일, '거래량']
    n_당일거래량ma60 = df_일봉.loc[dt_당일, '거래량ma60']
    n_당일거래량ma20 = df_일봉.loc[dt_당일, '거래량ma20']
    n_당일등락률 = df_일봉.loc[dt_당일, '전일대비(%)']

    # 선정조건 확인
    b_거래대금 = 100 < n_당일거래대금 < 1000            # 누적 26% (221/851)
    b_거래량60비 = n_당일거래량 > n_당일거래량ma60 * 3    # 누적 31% (135/441)
    b_거래량20비 = n_당일거래량 > n_당일거래량ma20 * 10   # 누적 38% (35/93)
    # b_등락률 = n_당일등락률 > 20                       # 누적 48% (12/27)

    # 결과 생성
    dic_종목선정 = df_일봉.loc[dt_당일].to_dict()
    dic_종목선정.update(당일거래대금=n_당일거래대금, 당일거래량=n_당일거래량, 당일거래량ma60=n_당일거래량ma60, 당일거래량ma20=n_당일거래량ma20,
                    종목선정=(b_거래대금 and b_거래량60비 and b_거래량20비),
                    거래대금=b_거래대금, 거래량60비=b_거래량60비, 거래량20비=b_거래량20비)

    return dic_종목선정


# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def judge_클로드20260519(df_일봉):
    # 기준정보 정의
    if len(df_일봉) < 2: return dict()
    dt_당일 = df_일봉.index[-1]
    n_당일등락률 = df_일봉.loc[dt_당일, '전일대비(%)']
    n_당일종가 = df_일봉.loc[dt_당일, '종가']
    n_당일종가ma20 = df_일봉.loc[dt_당일, '종가ma20']
    n_당일종가ma20비율 = n_당일종가 / n_당일종가ma20
    n_당일거래량 = df_일봉.loc[dt_당일, '거래량']
    n_당일거래량ma5 = df_일봉.loc[dt_당일, '거래량ma5']
    n_당일거래량ma5비율 = n_당일거래량 / n_당일거래량ma5

    # 선정조건 확인
    b_등락률 = 10 <= n_당일등락률 < 29.5
    b_종가ma20비율 = n_당일종가ma20비율 >= 1.3
    b_거래량ma5비율 = n_당일거래량ma5비율 >= 2

    # 결과 생성
    dic_종목선정 = df_일봉.loc[dt_당일].to_dict()
    dic_종목선정.update(당일등락률=n_당일등락률, 당일종가ma20비율=n_당일종가ma20비율, 당일거래량ma5비율=n_당일거래량ma5비율,
                    당일종가=n_당일종가, 당일종가ma20=n_당일종가ma20,
                    당일거래량=n_당일거래량, 당일거래량ma5=n_당일거래량ma5,
                    종목선정=(b_등락률 and b_종가ma20비율 and b_거래량ma5비율),
                    등락률=b_등락률, 종가ma20비율=b_종가ma20비율, 거래량ma5비율=b_거래량ma5비율)

    return dic_종목선정