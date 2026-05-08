import os
import json

import ut


# noinspection NonAsciiCharacters,PyPep8Naming,SpellCheckingInspection,PyUnreachableCode
class FolderManager:
    def __init__(self):
        # 기준폴더 정의
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 기준정보 생성
        self.dic_폴더정보 = dict(
            folder_work=dic_config['folder_work'],
            folder_log=dic_config['folder_log'],
            folder_kakao=dic_config['folder_kakao'],
            folder_kiwoom=dic_config['folder_kiwoom'])
        folder_work = self.dic_폴더정보['folder_work']

        # 매수매도 폴더 정의
        folder_매수매도 = os.path.join(folder_work, '매수매도')
        # self.dic_폴더정보['매수매도'] = os.path.join(folder_매수매도)
        self.dic_폴더정보.update(매수매도=os.path.join(folder_매수매도))
        self.dic_폴더정보['매수매도|종목잔고'] = os.path.join(folder_매수매도, '종목잔고_tr')
        self.dic_폴더정보['매수매도|신호탐색'] = os.path.join(folder_매수매도, '신호탐색')

        # 데이터 폴더 정의
        folder_데이터 = os.path.join(folder_work, '데이터')
        # self.dic_폴더정보['데이터'] = os.path.join(folder_데이터)
        self.dic_폴더정보.update(데이터=os.path.join(folder_데이터))
        self.dic_폴더정보['데이터|대상종목'] = os.path.join(folder_데이터, '대상종목')
        self.dic_폴더정보['데이터|조회순위'] = os.path.join(folder_데이터, '조회순위')
        self.dic_폴더정보['데이터|차트정보'] = os.path.join(folder_데이터, '차트정보')

        # 분석 폴더 정의
        folder_분석 = os.path.join(folder_work, '분석')
        # self.dic_폴더정보['분석'] = os.path.join(folder_분석)
        self.dic_폴더정보.update(분석=os.path.join(folder_분석))
        # self.dic_폴더정보['분석|종목추천'] = os.path.join(folder_분석, '종목추천')


if __name__ == '__main__':
    f = FolderManager()
    pass
