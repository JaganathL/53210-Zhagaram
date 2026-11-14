import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './core/auth.service';
import { ToastService } from './core/toast.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <div class="container topbar__inner">
        <a routerLink="/" class="brand" aria-label="ZHAGARAM Jewellery home">
          <span class="brand__mark">Z</span>
          <span class="brand__text">ZHAGARAM<small>Jewellery</small></span>
        </a>
        <nav class="nav">
          <a routerLink="/" routerLinkActive="is-active" [routerLinkActiveOptions]="{ exact: true }" [class.nav__home--admin]="auth.isAdmin()">Collection</a>
          @if (auth.isAdmin()) {
            <a routerLink="/admin" routerLinkActive="is-active">Dashboard</a>
            <button type="button" class="btn btn--ghost btn--sm" (click)="auth.logout()">Logout</button>
          } @else {
            <a routerLink="/admin/login" class="nav__admin" routerLinkActive="is-active" title="Admin login">
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path fill="currentColor" d="M12 1 3 5v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V5l-9-4Zm0 6a3 3 0 1 1 0 6 3 3 0 0 1 0-6Zm0 14c-2.5-.8-4.6-2.7-5.6-5 .9-1.5 3.3-2.5 5.6-2.5s4.7 1 5.6 2.5c-1 2.3-3.1 4.2-5.6 5Z"/>
              </svg>
              <span>Admin</span>
            </a>
          }
        </nav>
      </div>
    </header>

    <main class="container main">
      <router-outlet />
    </main>

    <footer class="footer">
      <div class="container footer__inner">
        <span>© {{ year }} ZHAGARAM Jewellery · Elegant designs, honest prices</span>
        <span class="footer__gold">Emerald Noir Collection</span>
      </div>
    </footer>

    <div class="toasts" aria-live="polite">
      @for (t of toast.toasts(); track t.id) {
        <div class="toast" [class.toast--error]="t.kind === 'error'" (click)="toast.dismiss(t.id)">{{ t.text }}</div>
      }
    </div>
  `,
})
export class AppComponent {
  protected readonly auth = inject(AuthService);
  protected readonly toast = inject(ToastService);
  protected readonly year = new Date().getFullYear();
}
