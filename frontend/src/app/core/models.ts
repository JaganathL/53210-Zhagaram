export type SortOption = 'newest' | 'price_asc' | 'price_desc' | 'name';

export interface CategoryInput {
  name: string;
  /** Rental categories are priced per day and have no MRP. */
  rental: boolean;
}

export interface Category extends CategoryInput {
  id: string;
  order: number;
  itemCount: number;
}

export interface PartInput {
  name: string;
  sku: string;
  category: string;
  brand: string;
  /** Price per day when the category is a rental category. */
  price: number;
  mrp: number | null;
  description: string;
  specs: Record<string, string>;
  imageUrl: string;
}

export interface Part extends PartInput {
  id: string;
  createdAt: string;
  updatedAt: string;
}

export interface PartQuery {
  search?: string;
  category?: string;
  sort?: SortOption;
}
