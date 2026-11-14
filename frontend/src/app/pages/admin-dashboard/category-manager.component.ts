import { Component, inject, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';
import { CategoriesService } from '../../core/categories.service';
import { Category } from '../../core/models';
import { ToastService, errorMessage } from '../../core/toast.service';

@Component({
  selector: 'app-category-manager',
  imports: [ReactiveFormsModule],
  template: `
    <div class="overlay" (click)="closed.emit()">
      <section class="drawer" role="dialog" aria-modal="true" aria-label="Manage categories" (click)="$event.stopPropagation()">
        <header class="drawer__head">
          <h2>Categories</h2>
          <button type="button" class="close" (click)="closed.emit()" aria-label="Close">×</button>
        </header>

        <div class="drawer__body">
          <form class="add" [formGroup]="addForm" (ngSubmit)="add()">
            <input class="input" formControlName="name" placeholder="New category, e.g. Toe Rings" aria-label="New category name" maxlength="40" />
            <label class="check"><input type="checkbox" formControlName="rental" /> Rental (₹ / day)</label>
            <button class="btn" type="submit" [disabled]="addForm.invalid || busy()">Add</button>
          </form>

          <ul class="list">
            @for (c of cats.categories(); track c.id) {
              <li class="row">
                @if (editingId() === c.id) {
                  <form class="edit" [formGroup]="editForm" (ngSubmit)="save(c)">
                    <input class="input" formControlName="name" aria-label="Category name" maxlength="40" />
                    <label class="check"><input type="checkbox" formControlName="rental" /> Rental</label>
                    <button class="btn btn--sm" type="submit" [disabled]="editForm.invalid || busy()">Save</button>
                    <button class="btn btn--light btn--sm" type="button" (click)="editingId.set(null)">Cancel</button>
                  </form>
                } @else if (deletingId() === c.id) {
                  <span class="row__name">Delete “{{ c.name }}”?</span>
                  <span class="row__actions">
                    <button class="btn btn--danger btn--sm" type="button" [disabled]="busy()" (click)="remove(c)">Delete</button>
                    <button class="btn btn--light btn--sm" type="button" (click)="deletingId.set(null)">Cancel</button>
                  </span>
                } @else {
                  <span class="row__name">
                    {{ c.name }}
                    @if (c.rental) { <span class="badge badge--rent">Rental</span> }
                  </span>
                  <span class="row__count">{{ c.itemCount }} item{{ c.itemCount === 1 ? '' : 's' }}</span>
                  <span class="row__actions">
                    <button class="btn btn--light btn--sm" type="button" (click)="startEdit(c)">Edit</button>
                    <button
                      class="btn btn--light btn--sm"
                      type="button"
                      [disabled]="c.itemCount > 0"
                      [title]="c.itemCount > 0 ? 'Move or delete its items first' : 'Delete category'"
                      (click)="deletingId.set(c.id)"
                    >Delete</button>
                  </span>
                }
              </li>
            } @empty {
              <li class="row row--empty">No categories yet.</li>
            }
          </ul>
          <p class="hint">A category can only be deleted when it has no items. Renaming updates all its items.</p>
        </div>
      </section>
    </div>
  `,
  styles: `
    .overlay { position: fixed; inset: 0; z-index: 50; background: rgb(14 20 17 / 55%); display: flex; justify-content: flex-end; }
    .drawer { width: 100%; max-width: 480px; height: 100%; background: var(--ivory-2); display: flex; flex-direction: column; box-shadow: -8px 0 24px rgb(0 0 0 / 20%); }
    .drawer__head { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--noir); border-bottom: 2px solid var(--gold); }
    .drawer__head h2 { color: var(--ivory); font-size: 18px; }
    .close { border: 0; background: none; color: var(--ivory); font-size: 24px; line-height: 1; cursor: pointer; }
    .drawer__body { flex: 1; min-height: 0; overflow-y: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; }
    .add, .edit { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .add .input, .edit .input { flex: 1 1 160px; min-width: 0; }
    .check { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--muted); white-space: nowrap; cursor: pointer; }
    .list { list-style: none; margin: 0; padding: 0; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); }
    .row { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid #efe8da; min-height: 46px; flex-wrap: wrap; }
    .row:last-child { border-bottom: 0; }
    .row .edit { flex: 1; }
    .row__name { flex: 1; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
    .row__count { font-size: 12px; color: var(--muted); }
    .row__actions { display: inline-flex; gap: 6px; }
    .row--empty { color: var(--muted); justify-content: center; }
    .hint { margin: 0; font-size: 12px; color: var(--muted); }
  `,
})
export class CategoryManagerComponent {
  protected readonly cats = inject(CategoriesService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder).nonNullable;

  readonly closed = output<void>();

  protected readonly busy = signal(false);
  protected readonly editingId = signal<string | null>(null);
  protected readonly deletingId = signal<string | null>(null);

  protected readonly addForm = this.fb.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40)]],
    rental: [false],
  });
  protected readonly editForm = this.fb.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40)]],
    rental: [false],
  });

  protected add(): void {
    const { name, rental } = this.addForm.getRawValue();
    this.run(this.cats.create({ name: name.trim(), rental }), `“${name.trim()}” added`, () =>
      this.addForm.reset({ name: '', rental: false }),
    );
  }

  protected startEdit(c: Category): void {
    this.deletingId.set(null);
    this.editForm.reset({ name: c.name, rental: c.rental });
    this.editingId.set(c.id);
  }

  protected save(c: Category): void {
    const { name, rental } = this.editForm.getRawValue();
    this.run(this.cats.update(c.id, { name: name.trim(), rental }), 'Category updated', () =>
      this.editingId.set(null),
    );
  }

  protected remove(c: Category): void {
    this.run(this.cats.delete(c.id), `“${c.name}” deleted`, () => this.deletingId.set(null));
  }

  private run(req: Observable<unknown>, ok: string, done: () => void): void {
    this.busy.set(true);
    req.subscribe({
      next: () => {
        this.toast.show(ok);
        this.busy.set(false);
        done();
      },
      error: (err) => {
        this.toast.show(errorMessage(err, 'Could not save category'), 'error');
        this.busy.set(false);
      },
    });
  }
}
