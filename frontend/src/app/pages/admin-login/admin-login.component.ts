import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { ToastService, errorMessage } from '../../core/toast.service';

@Component({
  selector: 'app-admin-login',
  imports: [ReactiveFormsModule],
  template: `
    <div class="login">
      <form class="panel login__card" [formGroup]="form" (ngSubmit)="submit()">
        <div class="login__mark">Z</div>
        <h1>Admin sign in</h1>
        <p class="login__sub">Manage the ZHAGARAM jewellery collection</p>

        <div class="field">
          <label for="username">Username</label>
          <input id="username" class="input" formControlName="username" autocomplete="username" />
        </div>
        <div class="field">
          <label for="password">Password</label>
          <div class="pw">
            <input
              id="password"
              class="input"
              [type]="showPw() ? 'text' : 'password'"
              formControlName="password"
              autocomplete="current-password"
            />
            <button type="button" class="pw__toggle" (click)="showPw.set(!showPw())">
              {{ showPw() ? 'Hide' : 'Show' }}
            </button>
          </div>
        </div>
        @if (error()) {
          <div class="error-text">{{ error() }}</div>
        }
        <button class="btn" type="submit" [disabled]="form.invalid || busy()">
          {{ busy() ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>
    </div>
  `,
  styles: `
    .login { display: grid; place-items: center; min-height: calc(100vh - 160px); }
    .login__card { width: 100%; max-width: 360px; padding: 24px; display: flex; flex-direction: column; gap: 12px; border-top: 3px solid var(--gold); }
    .login__mark { width: 44px; height: 44px; border-radius: 10px; display: grid; place-items: center; background: var(--noir); color: var(--gold); font: 700 22px var(--font-head); }
    h1 { font-size: 22px; }
    .login__sub { margin: -8px 0 4px; color: var(--muted); font-size: 13px; }
    .pw { position: relative; }
    .pw .input { padding-right: 56px; }
    .pw__toggle { position: absolute; right: 6px; top: 6px; height: 24px; border: 0; background: none; color: var(--emerald); font: 600 12px var(--font-body); cursor: pointer; }
  `,
})
export class AdminLoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly showPw = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    username: ['', Validators.required],
    password: ['', Validators.required],
  });

  constructor() {
    if (this.auth.isAdmin()) this.router.navigate(['/admin']);
  }

  submit(): void {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    const { username, password } = this.form.getRawValue();
    this.auth.login(username.trim(), password).subscribe({
      next: () => {
        this.toast.show('Welcome back, admin');
        this.router.navigate(['/admin']);
      },
      error: (err) => {
        this.error.set(err.status === 401 ? 'Invalid username or password' : errorMessage(err, 'Login failed'));
        this.busy.set(false);
      },
    });
  }
}
