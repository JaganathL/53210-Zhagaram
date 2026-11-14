import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { Category, CategoryInput } from './models';

/** Shared, signal-backed list of categories loaded from the API. */
@Injectable({ providedIn: 'root' })
export class CategoriesService {
  private readonly http = inject(HttpClient);

  readonly categories = signal<Category[]>([]);
  readonly loaded = signal(false);
  private readonly rentalNames = computed(
    () => new Set(this.categories().filter((c) => c.rental).map((c) => c.name)),
  );

  constructor() {
    this.refresh();
  }

  isRental(categoryName: string): boolean {
    return this.rentalNames().has(categoryName);
  }

  refresh(): void {
    this.http.get<Category[]>('/api/categories').subscribe({
      next: (list) => {
        this.categories.set(list);
        this.loaded.set(true);
      },
      error: () => this.loaded.set(true),
    });
  }

  create(input: CategoryInput): Observable<Category> {
    return this.http.post<Category>('/api/categories', input).pipe(tap(() => this.refresh()));
  }

  update(id: string, input: CategoryInput): Observable<Category> {
    return this.http
      .put<Category>(`/api/categories/${encodeURIComponent(id)}`, input)
      .pipe(tap(() => this.refresh()));
  }

  delete(id: string): Observable<void> {
    return this.http
      .delete<void>(`/api/categories/${encodeURIComponent(id)}`)
      .pipe(tap(() => this.refresh()));
  }
}
