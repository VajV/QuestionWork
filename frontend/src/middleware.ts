import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const isProfile = request.nextUrl.pathname.startsWith('/profile');
  if (isProfile) {
    const hasCookie = request.cookies.has('refresh_token');
    if (!hasCookie) {
      return NextResponse.redirect(new URL('/auth/login', request.url));
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/profile/:path*']
};
