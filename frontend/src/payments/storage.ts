// frontend/src/payments/storage.ts
// NEW FILE: Safe storage abstraction to replace localStorage

/**
 * Safe storage utility that works in all environments
 * Falls back to in-memory storage if sessionStorage is not available
 */

class SafeStorage {
  private memoryStore: Map<string, string> = new Map();
  private useSessionStorage: boolean = false;

  constructor() {
    // Test if sessionStorage is available
    try {
      const testKey = '__storage_test__';
      sessionStorage.setItem(testKey, 'test');
      sessionStorage.removeItem(testKey);
      this.useSessionStorage = true;
    } catch {
      console.warn('[Storage] sessionStorage not available, using in-memory fallback');
      this.useSessionStorage = false;
    }
  }

  setItem(key: string, value: string): void {
    try {
      if (this.useSessionStorage) {
        sessionStorage.setItem(key, value);
      } else {
        this.memoryStore.set(key, value);
      }
    } catch (error) {
      console.error('[Storage] Failed to set item:', error);
      this.memoryStore.set(key, value);
    }
  }

  getItem(key: string): string | null {
    try {
      if (this.useSessionStorage) {
        return sessionStorage.getItem(key);
      } else {
        return this.memoryStore.get(key) || null;
      }
    } catch (error) {
      console.error('[Storage] Failed to get item:', error);
      return this.memoryStore.get(key) || null;
    }
  }

  removeItem(key: string): void {
    try {
      if (this.useSessionStorage) {
        sessionStorage.removeItem(key);
      }
      this.memoryStore.delete(key);
    } catch (error) {
      console.error('[Storage] Failed to remove item:', error);
      this.memoryStore.delete(key);
    }
  }

  clear(): void {
    try {
      if (this.useSessionStorage) {
        sessionStorage.clear();
      }
      this.memoryStore.clear();
    } catch (error) {
      console.error('[Storage] Failed to clear storage:', error);
      this.memoryStore.clear();
    }
  }
}

// Export singleton instance
export const storage = new SafeStorage();

}