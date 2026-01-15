import React, { cache } from 'react';
import { setRequestLocale } from 'next-intl/server';

import { OffersApi } from 'src/api';
import { injectToken } from 'src/api/client';
import { auth } from 'src/auth';
import { Loader } from 'src/components';
import { Locale } from 'src/navigation';

import style from './Offer.module.scss';

const getData = cache(async (id: number) => {
  const session = await auth();
  injectToken(session?.access_token);
  const { data } = await OffersApi.getOffer(id);

  return data;
});

export const generateMetadata = async ({
  params
}: {
  params: Promise<{ id: string }>;
}) => {
  const { id } = await params;
  const data = await getData(+id);

  return {
    title: data.title,
    description: data.description,
    image: data.image,
    openGraph: {
      images: data.image
    }
  };
};

const Offer = async ({
  params
}: Readonly<{ params: Promise<{ locale: Locale; id: string }> }>) => {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const session = await auth();
  const data = await getData(+id);

  if (!data) return <Loader />;
  return (
    <div>
      <h1>Offer</h1>

      <h2>{data.title}</h2>
      <p>{data.description}</p>
      {session?.user && <b>{session.user.email}</b>}
    </div>
  );
};

export default Offer;
