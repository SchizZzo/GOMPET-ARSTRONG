'use client';

import React from 'react';
import { useFormState, useFormStatus } from 'react-dom';
import { useTranslations } from 'next-intl';

import { Button, Input, Loader } from 'src/components';

import { passwordReset, PasswordResetFormState } from './actions';

import style from './PasswordForgetReset.module.scss';

const PasswordForgetResetForm = () => {
  const t = useTranslations();

  const [state, action] = useFormState<PasswordResetFormState>(passwordReset, {
    message: '',
    errors: undefined,
    fields: {
      password: '',
      passwordRepeat: ''
    }
  });

  return (
    <form
      className={style.form}
      action={action}
    >
      <PasswordResetFields state={state} />
    </form>
  );
};

const PasswordResetFields = ({ state }: { state: PasswordResetFormState }) => {
  const { pending } = useFormStatus();

  return (
    <>
      <Input
        type='password'
        key={'password'}
        name='password'
        label='Nowe hasło'
        placeholder='Utwórz nowe hasło'
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
      <Button
        type='submit'
        label='Ustaw nowe hasło'
        isLoading={pending}
      />
      {pending && <Loader />}
    </>
  );
};

export default PasswordForgetResetForm;
