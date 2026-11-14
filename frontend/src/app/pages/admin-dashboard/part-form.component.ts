import { Component, OnInit, inject, input, output, signal } from '@angular/core';
import { FormArray, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CategoriesService } from '../../core/categories.service';
import { Part, PartInput } from '../../core/models';
import { PartsService } from '../../core/parts.service';
import { ToastService, errorMessage } from '../../core/toast.service';

const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

@Component({
  selector: 'app-part-form',
  imports: [ReactiveFormsModule],
  templateUrl: './part-form.component.html',
  styleUrl: './part-form.component.scss',
})
export class PartFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly parts = inject(PartsService);
  private readonly toast = inject(ToastService);

  readonly part = input<Part | null>(null);
  readonly saved = output<{ part: Part; isNew: boolean }>();
  readonly closed = output<void>();

  protected readonly cats = inject(CategoriesService);
  protected readonly saving = signal(false);
  protected readonly uploading = signal(false);
  protected readonly serverError = signal('');

  protected readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    sku: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40)]],
    category: ['', Validators.required],
    brand: ['', [Validators.required, Validators.maxLength(60)]],
    price: [0, [Validators.required, Validators.min(1)]],
    mrp: [null as number | null, Validators.min(1)],
    description: ['', Validators.maxLength(2000)],
    imageUrl: [''],
    specs: this.fb.array<ReturnType<PartFormComponent['specRow']>>([]),
  });

  get specs(): FormArray {
    return this.form.controls.specs;
  }

  protected isRent(): boolean {
    return this.cats.isRental(this.form.controls.category.value);
  }

  ngOnInit(): void {
    const p = this.part();
    if (!p) {
      const first = this.cats.categories().find((c) => !c.rental) ?? this.cats.categories()[0];
      this.form.patchValue({ category: first?.name ?? '' });
      this.addSpec();
      return;
    }
    this.form.patchValue({
      name: p.name,
      sku: p.sku,
      category: p.category,
      brand: p.brand,
      price: p.price,
      mrp: p.mrp,
      description: p.description,
      imageUrl: p.imageUrl,
    });
    Object.entries(p.specs).forEach(([k, v]) => this.addSpec(k, v));
  }

  private specRow(key = '', value = '') {
    return this.fb.group({ key: [key, Validators.maxLength(40)], value: [value, Validators.maxLength(80)] });
  }

  protected addSpec(key = '', value = ''): void {
    this.form.controls.specs.push(this.specRow(key, value));
  }

  protected removeSpec(i: number): void {
    this.form.controls.specs.removeAt(i);
  }

  protected onFile(event: Event): void {
    const inputEl = event.target as HTMLInputElement;
    const file = inputEl.files?.[0];
    inputEl.value = '';
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) {
      this.toast.show('Only JPG, PNG or WEBP images are allowed', 'error');
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      this.toast.show('Image must be 2 MB or smaller', 'error');
      return;
    }
    this.uploading.set(true);
    this.parts.upload(file).subscribe({
      next: ({ imageUrl }) => {
        this.form.patchValue({ imageUrl });
        this.uploading.set(false);
      },
      error: (err) => {
        this.toast.show(errorMessage(err, 'Upload failed'), 'error');
        this.uploading.set(false);
      },
    });
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const payload: PartInput = {
      name: v.name.trim(),
      sku: v.sku.trim().toUpperCase(),
      category: v.category,
      brand: v.brand.trim(),
      price: Number(v.price),
      // MRP / discount does not apply to rentals.
      mrp: !this.isRent() && v.mrp ? Number(v.mrp) : null,
      description: v.description.trim(),
      imageUrl: v.imageUrl,
      specs: Object.fromEntries(
        v.specs.filter((s) => s.key.trim() && s.value.trim()).map((s) => [s.key.trim(), s.value.trim()]),
      ),
    };

    const existing = this.part();
    this.saving.set(true);
    this.serverError.set('');
    const req = existing ? this.parts.update(existing.id, payload) : this.parts.create(payload);
    req.subscribe({
      next: (part) => this.saved.emit({ part, isNew: !existing }),
      error: (err) => {
        this.serverError.set(errorMessage(err, 'Save failed'));
        this.saving.set(false);
      },
    });
  }

  protected invalid(name: keyof typeof this.form.controls): boolean {
    const c = this.form.controls[name];
    return c.invalid && c.touched;
  }
}
