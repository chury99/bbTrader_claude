import os
import json

import ut.도구manager


# noinspection PyPep8Naming,NonAsciiCharacters,SpellCheckingInspection
def define_폴더정보():
    # config 읽어 오기
    folder_베이스 = os.path.dirname(os.path.abspath(__file__))
    folder_프로젝트 = os.path.dirname(folder_베이스)
    # dic_config = json.load(open(os.path.join(folder_프로젝트, 'config.json'), mode='rt', encoding='utf-8'))
    dic_config = ut.도구manager.ToolManager().config로딩()

    # 기준정보 생성
    dic_폴더정보 = dict()
    dic_폴더정보['folder_work'] = dic_config['folder_work']
    dic_폴더정보['folder_log'] = dic_config['folder_log']
    dic_폴더정보['folder_kakao'] = dic_config['folder_kakao']
    dic_폴더정보['folder_kiwoom'] = dic_config['folder_kiwoom']
    folder_work = dic_폴더정보['folder_work']

    # 매수매도 폴더 정의
    folder_매수매도 = os.path.join(folder_work, '매수매도')
    dic_폴더정보['매수매도'] = os.path.join(folder_매수매도)
    dic_폴더정보['매수매도|종목잔고'] = os.path.join(folder_매수매도, '종목잔고_tr')

    # dic_폴더정보['매수매도|감시종목'] = os.path.join(folder_매수매도, '감시종목_sp')
    # dic_폴더정보['매수매도|주문체결'] = os.path.join(folder_매수매도, '주문체결_ws')

    # 데이터 폴더 정의
    folder_데이터 = os.path.join(folder_work, '데이터')
    dic_폴더정보['데이터'] = os.path.join(folder_데이터)

    # dic_폴더정보['데이터|차트수집'] = os.path.join(folder_데이터, '차트수집_tr')
    # dic_폴더정보['데이터|주식체결'] = os.path.join(folder_데이터, '주식체결_ws')
    # dic_폴더정보['데이터|전체종목'] = os.path.join(folder_데이터, '전체종목_tr')
    # dic_폴더정보['데이터|조건검색'] = os.path.join(folder_데이터, '조건검색_ws')
    # dic_폴더정보['데이터|대상종목'] = os.path.join(folder_데이터, '대상종목')
    # dic_폴더정보['데이터|조회순위'] = os.path.join(folder_데이터, '조회순위_tr')
    # dic_폴더정보['데이터|종목추천'] = os.path.join(folder_데이터, '종목추천')
    # dic_폴더정보['데이터|종목관리'] = os.path.join(folder_데이터, '종목관리')
    # dic_폴더정보['데이터|차트캐시'] = os.path.join(folder_데이터, '차트캐시')

    # 분석 폴더 정의
    folder_분석 = os.path.join(folder_work, '분석')
    dic_폴더정보['분석'] = os.path.join(folder_분석)

    # dic_폴더정보['분석|백테스팅'] = os.path.join(folder_분석, '백테스팅')
    # dic_폴더정보['분석|일봉분석'] = os.path.join(folder_분석, '일봉분석')

    return dic_폴더정보
