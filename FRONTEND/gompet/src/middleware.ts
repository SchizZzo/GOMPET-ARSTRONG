import { NextRequest, NextResponse } from 'next/server';
import createIntlMiddleware from 'next-intl/middleware';

import { auth } from 'src/auth';

import { PROTECTED_ROUTES, PUBLIC_ONLY_ROUTES, Routes } from './constants/routes';

const locales = ['pl'];

const intlMiddleware = createIntlMiddleware({
  locales,
  defaultLocale: 'pl',
  localePrefix: 'as-needed'
});

const testPagesRegex = (pages: string[], pathname: string) => {
  const regex = `^(/(${locales.join('|')}))?(${pages.map((p) => p.replace('/*', '.*')).join('|')})/?$`;
  return new RegExp(regex, 'i').test(pathname);
};

const withCurrentPath = (req: NextRequest, response: NextResponse) => {
  response.headers.set('x-current-path', req.nextUrl.pathname);
  return response;
};

const handleAuth = async (req: NextRequest, isPublicOnlyPage: boolean, isProtectedPage: boolean) => {
<<<<<<< HEAD
  const session = await auth();
  const isAuth = !!session?.user;
=======
  if (!isPublicOnlyPage && !isProtectedPage) {
    return withCurrentPath(req, intlMiddleware(req));
  }

  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  const isAuth = Boolean(token?.access_token || token?.user);
>>>>>>> ee92d2c4f2317116d85e63fdba3e771a7ac81a4c

  if (!isAuth && isProtectedPage) {
    let from = req.nextUrl.pathname;
    if (req.nextUrl.search) {
      from += req.nextUrl.search;
    }

    return withCurrentPath(req, NextResponse.redirect(new URL(`${Routes.LOGIN}?from=${encodeURIComponent(from)}`, req.url)));
  }

  if (isAuth && isPublicOnlyPage) {
    return withCurrentPath(req, NextResponse.redirect(new URL(Routes.LANDING, req.nextUrl)));
  }

  return withCurrentPath(req, intlMiddleware(req));
};

export default async function middleware(req: NextRequest) {
  const isPublicOnlyPage = testPagesRegex(PUBLIC_ONLY_ROUTES, req.nextUrl.pathname);
  const isProtectedPage = testPagesRegex(PROTECTED_ROUTES, req.nextUrl.pathname);

  return await handleAuth(req, isPublicOnlyPage, isProtectedPage);
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)']
};
