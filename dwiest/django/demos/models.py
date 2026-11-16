"""Register Inventory models when the demos umbrella app is installed."""
from .inventory.models import InventoryEntry, InventoryItem, InventoryList, InventoryTransaction
from .bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis, BookmarkAIAttempt, BookmarkEnrichmentAttempt
