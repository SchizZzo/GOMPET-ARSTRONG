'use client';

import React from 'react';
import { useFormState, useFormStatus } from 'react-dom';
import { useTranslations } from 'next-intl';

import { Button, Input, Loader } from 'src/components';

import { passwordForget, PasswordForgetFormState } from './actions';

import style from './PasswordForget.module.scss';

const PasswordForgetForm = () => {
  const t = useTranslations();

  const [state, action] = useFormState<PasswordForgetFormState>(passwordForget, {
    message: '',
    errors: undefined,
    fields: {
      email: ''
    }
  });

  return (
    <form
      className={style.form}
      action={action}
    >
      <PasswordForgetFields state={state} />
    </form>
  );
};

const PasswordForgetFields = ({ state }: { state: PasswordForgetFormState }) => {
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
      <Button
        type='submit'
        label='Wyślij link do resetu hasła'
        isLoading={pending}
      />
      {pending && <Loader />}
    </>
  );
};

export default PasswordForgetForm;
