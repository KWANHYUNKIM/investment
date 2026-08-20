"""모든 모델을 한 곳에서 import 한다 — Alembic 이 metadata 를 볼 수 있게.

여기서 빠뜨린 모델은 마이그레이션 자동생성에서 조용히 사라진다. 그래서 새 모델을
만들면 반드시 이 목록에 넣는다.
"""
from app.db.models.budget import (Card, Category, ImportBatch, IncomeProfile,
                                  MailMessage, MerchantRule, Transaction)
from app.db.models.identity import (AppUser, AuditEvent, EmailVerification,
                                    UserCredential)
from app.db.models.market import CompanyProfile, Security
from app.db.models.ops import (ApiQuotaUsage, BatchRun, DatasetSnapshot,
                               PageViewDaily)
from app.db.models.portfolio import Holding, WatchItem, WealthProfile
from app.db.models.realestate import (InterestPoint, InterestRun, Region,
                                      RegionMonthAreaStat, RegionMonthStat)

__all__ = [
    "AppUser", "ApiQuotaUsage", "AuditEvent", "BatchRun", "Card", "Category",
    "CompanyProfile", "DatasetSnapshot", "EmailVerification", "Holding",
    "ImportBatch", "IncomeProfile", "InterestPoint", "InterestRun", "MailMessage",
    "MerchantRule", "PageViewDaily", "Region", "RegionMonthAreaStat",
    "RegionMonthStat", "Security", "Transaction", "UserCredential",
    "WatchItem", "WealthProfile",
]
