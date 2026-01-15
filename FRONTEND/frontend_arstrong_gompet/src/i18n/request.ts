import { notFound } from 'next/navigation';
import { getRequestConfig } from 'next-intl/server';
import { Locale, locales } from 'src/navigation';

const loaders: Record<Locale, () => Promise<any>> = {
  pl: async () => ({
    common: (await import('../../locales/pl/common.json')).default,
    error: (await import('../../locales/pl/error.json')).default,
    form: (await import('../../locales/pl/form.json')).default,
    navigation: (await import('../../locales/pl/navigation.json')).default,
    notifications: (await import('../../locales/pl/notifications.json')).default,

    landing: (await import('../../locales/pl/pages/landing.json')).default,
    animals: (await import('../../locales/pl/pages/animals.json')).default,
    organizations: (await import('../../locales/pl/pages/organizations.json')).default,

    authLogin: (await import('../../locales/pl/pages/auth/login.json')).default,
    authSignup: (await import('../../locales/pl/pages/auth/signup.json')).default,
    authPasswordForget: (await import('../../locales/pl/pages/auth/password-forget.json')).default,
    authPasswordForgetReset: (await import('../../locales/pl/pages/auth/password-forget-reset.json')).default,
    authVerifyEmail: (await import('../../locales/pl/pages/auth/verify-email.json')).default,
    authVerifyEmailCheckValid: (await import('../../locales/pl/pages/auth/verify-email-check-valid.json')).default
  })
};

export default getRequestConfig(async ({ locale }) => {
  if (!locales.includes(locale as Locale)) notFound();
  const l = locale as Locale;

  const messages = await loaders[l]();

  return { messages };
});
