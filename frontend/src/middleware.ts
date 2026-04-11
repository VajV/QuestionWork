import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PROTECTED_PREFIXES = [
  '/profile',
  '/quests/create',
  '/notifications',
  '/messages',
  '/admin',
  '/disputes',
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + '/'));
  if (isProtected) {
    const hasCookie = request.cookies.has('refresh_token');
    if (!hasCookie) {
      return NextResponse.redirect(new URL('/auth/login', request.url));
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    '/profile/:path*',
    '/quests/create',
    '/notifications/:path*',
    '/messages/:path*',
    '/admin/:path*',
    '/disputes/:path*',
  ],
};
