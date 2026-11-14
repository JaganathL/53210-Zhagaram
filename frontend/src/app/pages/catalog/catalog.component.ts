import { CurrencyPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { rxResource, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged } from 'rxjs';
import { CategoriesService } from '../../core/categories.service';
import { Part, SortOption } from '../../core/models';
import { PartsService } from '../../core/parts.service';

@Component({
  selector: 'app-catalog',
  imports: [RouterLink, CurrencyPipe],
  templateUrl: './catalog.component.html',
  styleUrl: './catalog.component.scss',
})
export class CatalogComponent {
  private readonly parts = inject(PartsService);

  protected readonly cats = inject(CategoriesService);
  protected readonly search = signal('');
  protected readonly category = signal('');
  protected readonly sort = signal<SortOption>('newest');
  private readonly debouncedSearch = toSignal(
    toObservable(this.search).pipe(debounceTime(250), distinctUntilChanged()),
    { initialValue: '' },
  );

  protected readonly resource = rxResource({
    request: () => ({ search: this.debouncedSearch(), category: this.category(), sort: this.sort() }),
    loader: ({ request }) => this.parts.list(request),
  });
  protected readonly items = computed<Part[]>(() => this.resource.value() ?? []);
  protected readonly skeletons = Array.from({ length: 8 });

  protected discount(p: Part): number {
    return p.mrp && p.mrp > p.price ? Math.round(((p.mrp - p.price) / p.mrp) * 100) : 0;
  }

  protected reset(): void {
    this.search.set('');
    this.category.set('');
    this.sort.set('newest');
  }
}
