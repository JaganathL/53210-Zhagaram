import { CurrencyPipe, KeyValuePipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { CategoriesService } from '../../core/categories.service';
import { PartsService } from '../../core/parts.service';

@Component({
  selector: 'app-part-detail',
  imports: [RouterLink, CurrencyPipe, KeyValuePipe],
  templateUrl: './part-detail.component.html',
  styleUrl: './part-detail.component.scss',
})
export class PartDetailComponent {
  private readonly parts = inject(PartsService);
  protected readonly auth = inject(AuthService);
  protected readonly cats = inject(CategoriesService);

  readonly id = input.required<string>();
  protected readonly resource = rxResource({
    request: () => this.id(),
    loader: ({ request }) => this.parts.get(request),
  });
  protected readonly part = computed(() => this.resource.value());
  protected readonly discount = computed(() => {
    const p = this.part();
    return p?.mrp && p.mrp > p.price ? Math.round(((p.mrp - p.price) / p.mrp) * 100) : 0;
  });
  protected readonly unordered = () => 0;

  /** Server-side download (Content-Disposition) for images stored in the database. */
  protected readonly downloadUrl = computed(() => {
    const p = this.part();
    if (!p?.imageUrl.startsWith('/api/images/')) return null;
    const name = p.name.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase();
    return `${p.imageUrl}/download?filename=${encodeURIComponent(`zhagaram-${name}`)}`;
  });
}
