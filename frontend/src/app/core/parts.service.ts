import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Part, PartInput, PartQuery } from './models';

@Injectable({ providedIn: 'root' })
export class PartsService {
  private readonly http = inject(HttpClient);

  list(query: PartQuery = {}): Observable<Part[]> {
    let params = new HttpParams();
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.category) params = params.set('category', query.category);
    if (query.sort) params = params.set('sort', query.sort);
    return this.http.get<Part[]>('/api/parts', { params });
  }

  get(id: string): Observable<Part> {
    return this.http.get<Part>(`/api/parts/${encodeURIComponent(id)}`);
  }

  create(part: PartInput): Observable<Part> {
    return this.http.post<Part>('/api/parts', part);
  }

  update(id: string, part: PartInput): Observable<Part> {
    return this.http.put<Part>(`/api/parts/${encodeURIComponent(id)}`, part);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`/api/parts/${encodeURIComponent(id)}`);
  }

  upload(file: File): Observable<{ imageUrl: string }> {
    const body = new FormData();
    body.append('file', file);
    return this.http.post<{ imageUrl: string }>('/api/uploads', body);
  }
}
