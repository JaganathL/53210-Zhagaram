import { CurrencyPipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { CategoriesService } from '../../core/categories.service';
import { Part } from '../../core/models';
import { PartsService } from '../../core/parts.service';
import { ToastService, errorMessage } from '../../core/toast.service';
import { CategoryManagerComponent } from './category-manager.component';
import { PartFormComponent } from './part-form.component';

@Component({
  selector: 'app-admin-dashboard',
  imports: [CurrencyPipe, RouterLink, PartFormComponent, CategoryManagerComponent],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.scss',
})
export class AdminDashboardComponent {
  private readonly parts = inject(PartsService);
  private readonly toast = inject(ToastService);
  private readonly router = inject(Router);
  protected readonly cats = inject(CategoriesService);

  /** Optional `?edit=<id>` deep link from the detail page. */
  readonly edit = input<string>();

  protected readonly resource = rxResource({ loader: () => this.parts.list({ sort: 'newest' }) });
  protected readonly filter = signal('');
  protected readonly items = computed(() => {
    const term = this.filter().trim().toLowerCase();
    const all = this.resource.value() ?? [];
    return term
      ? all.filter((p) => `${p.name} ${p.sku} ${p.brand} ${p.category}`.toLowerCase().includes(term))
      : all;
  });
  protected readonly stats = computed(() => {
    const all = this.resource.value() ?? [];
    return {
      total: all.length,
      rent: all.filter((p) => this.cats.isRental(p.category)).length,
      sale: all.filter((p) => !this.cats.isRental(p.category)).length,
      categories: this.cats.categories().length,
    };
  });

  protected readonly editing = signal<Part | null | undefined>(undefined);
  protected readonly confirmDelete = signal<Part | null>(null);
  protected readonly deleting = signal(false);
  protected readonly managingCategories = signal(false);

  protected readonly editTarget = computed(() => {
    const id = this.edit();
    const all = this.resource.value();
    return id && all ? all.find((p) => p.id === id) : undefined;
  });

  constructor() {
    // Open the edit form once the deep-linked part has loaded, then drop the query param.
    effect(() => {
      const target = this.editTarget();
      if (target) {
        untracked(() => this.editing.set(target));
        this.router.navigate([], { queryParams: {}, replaceUrl: true });
      }
    });
  }

  protected openNew(): void {
    this.editing.set(null);
  }

  protected onSaved(part: Part, isNew: boolean): void {
    this.editing.set(undefined);
    this.toast.show(isNew ? `“${part.name}” added` : `“${part.name}” updated`);
    this.resource.reload();
    this.cats.refresh();
  }

  protected remove(): void {
    const part = this.confirmDelete();
    if (!part) return;
    this.deleting.set(true);
    this.parts.delete(part.id).subscribe({
      next: () => {
        this.toast.show(`“${part.name}” deleted`);
        this.confirmDelete.set(null);
        this.deleting.set(false);
        this.resource.reload();
        this.cats.refresh();
      },
      error: (err) => {
        this.toast.show(errorMessage(err, 'Delete failed'), 'error');
        this.deleting.set(false);
      },
    });
  }
}
