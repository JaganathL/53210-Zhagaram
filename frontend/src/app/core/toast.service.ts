import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  text: string;
  kind: 'success' | 'error';
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<Toast[]>([]);
  private nextId = 0;

  show(text: string, kind: Toast['kind'] = 'success'): void {
    const toast = { id: ++this.nextId, text, kind };
    this.toasts.update((list) => [...list, toast]);
    setTimeout(() => this.dismiss(toast.id), 3200);
  }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
  }
}

export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) {
    return `${detail[0].loc?.at(-1) ?? 'Field'}: ${detail[0].msg}`;
  }
  return fallback;
}
