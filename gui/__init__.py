"""PySide6 데스크톱 GUI — Qt Model/View 기반 MVC 구조.

계층 분리(실무형):
    services/    백엔드 FastAPI 호출 (데이터 접근 계층)
    models/      Qt 모델 (QAbstractTableModel 등 — View 에 데이터 공급)
    views/       위젯/UI 만 담당 (로직 없음)
    controllers/ View 이벤트 ↔ service/model 연결 (오케스트레이션)

진입점은 gui.main:main.
"""
