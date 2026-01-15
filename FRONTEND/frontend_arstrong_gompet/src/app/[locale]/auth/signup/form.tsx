'use client';

import React, { useEffect, useState } from 'react';
import { useFormState, useFormStatus } from 'react-dom';
import { useTranslations } from 'next-intl';

import { Button, Checkbox, Input, Loader } from 'src/components';
import { Routes } from 'src/constants/routes';
import { Link } from 'src/navigation';

import { signup, SignupFormState } from './actions';

import style from './SignUp.module.scss';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';


const SignUpForm = () => {
  const t = useTranslations();
  const router = useRouter();

  const [state, action] = useFormState<SignupFormState>(signup, {
    message: '',
    errors: undefined,
    text: '',
    fields: {
      email: '',
      firstName: '',
      lastName: '',
      password: '',
      passwordRepeat: '',
      statute: false
    }
  });

  const [locationAlowed, setLocationAllowed] = useState<boolean>(false)
  const [location, setLocation] = useState<{
    type: 'Point';
    coordinates: [number, number];
  } | null>(null);


  useEffect(() => {
    if(state.message == 'error'){
      toast.error(state.errors?.email || "Wystąpił błąd.");
    }
    console.log(state)

    if (state.message === 'success') {
      toast.success(state.text || "Profile zostal stworzony");
      router.push('/auth/login');
    }
  }, [state.message, router]);

  return (
    <form
      className={style.form}
      action={action}
    >
      <SignUpFields
        state={state}
        location={location}
        locationAlowed={locationAlowed}
        setLocationAllowed={setLocationAllowed}
        setLocation={setLocation}
        t={t}
      />
    </form>
  );
};

const SignUpFields = ({
  state,
  location,
  locationAlowed,
  setLocationAllowed,
  setLocation,
  t,
}: {
  state: SignupFormState;
  location: {
    type: 'Point';
    coordinates: [number, number];
  } | null;
  locationAlowed: boolean;
  setLocationAllowed: React.Dispatch<React.SetStateAction<boolean>>;
  setLocation: React.Dispatch<
    React.SetStateAction<{
      type: 'Point';
      coordinates: [number, number];
    } | null>
  >;
  t: ReturnType<typeof useTranslations>;
}) => {
  const { pending } = useFormStatus();

  return (
    <>
      <Input
        type='email'
        key={'email'}
        name='email'
        label='Email'
        placeholder='Wpisz swój email'
        defaultValue={state.fields.email}
      />
      <Input
        key={'firstName'}
        name='firstName'
        label='Imię'
        placeholder='Wpisz swoje imię'
        defaultValue={state.fields.firstName}
      />
      <Input
        key={'lastName'}
        name='lastName'
        label='Nazwisko'
        placeholder='Wpisz swoje nazwisko'
        defaultValue={state.fields.lastName}
      />
      <Input
        type='password'
        key={'password'}
        name='password'
        label='Hasło'
        placeholder='Utwórz hasło'
        defaultValue={state.fields.password}
      />
      <Input
        type='password'
        key={'passwordRepeat'}
        name='passwordRepeat'
        label='Powtórz hasło'
        placeholder='Powtórz hasło'
        defaultValue={state.fields.passwordRepeat}
      />
      <Checkbox
        id="location"
        label="Czy możemy korzystać z twojej lokalizacji"
        checked={locationAlowed}
        onChange={async (e: any) => {
          const checked = e.target.checked;
          setLocationAllowed(checked);

          if (!checked) {
            setLocation(null);
            return;
          }

          try {
            const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
              if (!navigator.geolocation) {
                reject(new Error('Geolocation not supported'));
                return;
              }

              navigator.geolocation.getCurrentPosition(
                (position) => resolve(position),
                (error) => reject(error),
                {
                  enableHighAccuracy: true,
                  timeout: 10000,
                }
              );
            });
            setLocation({
              type: 'Point',
              coordinates: [
                pos.coords.longitude,
                pos.coords.latitude,
              ],
            });
          } catch {
            toast.error('Nie udało się pobrać lokalizacji');
            setLocationAllowed(false);
          }
        }}
      />
      {location && (
        <input
          type="hidden"
          name="location"
          value={JSON.stringify(location)}
        />
      )}
      <Checkbox
        id='statute'
        name='statute'
        label={t.rich('form.termsAndConditions', {
          statute: (chunks) => (
            <Link
              href={Routes.DOC_STATUTE}
              className={style.link}
            >
              {chunks}
            </Link>
          ),
          privacy: (chunks) => (
            <Link
              href={Routes.DOC_PRIVACY}
              className={style.link}
            >
              {chunks}
            </Link>
          )
        })}
        defaultChecked={state.fields.statute}
      />
      <Button
        type='submit'
        label='Utwórz konto'
        isLoading={pending}
      />
      {pending && <Loader />}
    </>
  );
};

export default SignUpForm;
