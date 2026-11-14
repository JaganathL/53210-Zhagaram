import { Routes } from '@angular/router';
import { adminGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: '',
    title: 'ZHAGARAM Jewellery',
    loadComponent: () => import('./pages/catalog/catalog.component').then((m) => m.CatalogComponent),
  },
  {
    path: 'parts/:id',
    title: 'Jewellery details · ZHAGARAM',
    loadComponent: () =>
      import('./pages/part-detail/part-detail.component').then((m) => m.PartDetailComponent),
  },
  {
    path: 'admin/login',
    title: 'Admin login · ZHAGARAM',
    loadComponent: () =>
      import('./pages/admin-login/admin-login.component').then((m) => m.AdminLoginComponent),
  },
  {
    path: 'admin',
    title: 'Admin · ZHAGARAM',
    canActivate: [adminGuard],
    loadComponent: () =>
      import('./pages/admin-dashboard/admin-dashboard.component').then(
        (m) => m.AdminDashboardComponent,
      ),
  },
  { path: '**', redirectTo: '' },
];
