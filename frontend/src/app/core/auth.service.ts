import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

interface TokenResponse {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
}

interface StoredSession {
  token: string;
  expiresAt: number;
}

const STORAGE_KEY = 'zha_admin_session';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly session = signal<StoredSession | null>(this.restore());

  readonly isAdmin = computed(() => {
    const s = this.session();
    return !!s && s.expiresAt > Date.now();
  });

  get token(): string | null {
    const s = this.session();
    return s && s.expiresAt > Date.now() ? s.token : null;
  }

  login(username: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/api/auth/login', { username, password }).pipe(
      tap((res) => {
        const session = { token: res.accessToken, expiresAt: Date.now() + res.expiresIn * 1000 };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
        this.session.set(session);
      }),
    );
  }

  logout(redirect = true): void {
    sessionStorage.removeItem(STORAGE_KEY);
    this.session.set(null);
    if (redirect) this.router.navigate(['/admin/login']);
  }

  private restore(): StoredSession | null {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as StoredSession) : null;
      return parsed && parsed.expiresAt > Date.now() ? parsed : null;
    } catch {
      return null;
    }
  }
}
