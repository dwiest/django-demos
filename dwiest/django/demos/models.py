"""Register Inventory models when the demos umbrella app is installed."""
from .inventory.models import InventoryEntry, InventoryItem, InventoryList, InventoryTransaction
from .bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis, BookmarkAIAttempt, BookmarkEnrichmentAttempt

# Register the historical umbrella models during app loading, not only on URL imports.
# Otherwise makemigrations can mistake lazily loaded tables for deleted models.
from .bookmarks.models import Bookmark, Tag, BookmarkTag
from .file.models import File, FileQuota, FileSummary
from .journal.models import Journal, JournalEntry
from .news.models import NewsItem
from .invoicer.models import BillTo, Invoice, LineItem
from .expenses.models import ExpenseList, ExpenseCategory, Expense
from .application_models import Application

