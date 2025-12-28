'use client';

import React, { useEffect, useState } from 'react';
import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';

import { Button, Input } from 'src/components';
import { Params } from 'src/constants/params';
import { Routes } from 'src/constants/routes';
import { useRouter } from 'src/navigation';

import style from './Login.module.scss';
import toast from 'react-hot-toast';

type Fields = {
  email: string;
  password: string;
};

type ErrorData = {
  error?: {
    message?: string;
    errors?: {
      email?: string;
      password?: string;
    };
  };
};

type LoginFormState = {
  errorData?: ErrorData;
  message: string;
  errors: Record<keyof Fields, string> | undefined;
  fields: Fields;
};

const LoginForm = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [state, setState] = useState<LoginFormState>({
    message: '',
    errors: undefined,
    fields: {
      email: '',
      password: ''
    }
  });
  const [isPending, setIsPending] = useState(false);

  useEffect(() => {
    const redirectedFrom = searchParams.get(Params.FROM);

    if(state.message == 'error'){
      if(state.errors?.email) toast.error('Email is required');
      if(state.errors?.password) toast.error('Password is required');
    }
    
    if (state.message == 'wrong') {
      toast.error("Nie udalo się zalogowac");
    }

    if (state.message === 'success') {
      // toast.success('Witamy na stronie!');
      if (redirectedFrom) {
        router.replace(redirectedFrom);
      } else {
        router.replace(Routes.LOGIN_REDIRECT);
      }
    }
  }, [state.errors, state.message, searchParams, router]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isPending) return;

    const formData = new FormData(event.currentTarget);
    const email = formData.get('email') as string;
    const password = formData.get('password') as string;

    const fields = { email, password };

    if (!email || !password) {
      setState({
        message: 'error',
        errors: {
          email: email ? '' : 'Email is required',
          password: password ? '' : 'Password is required'
        },
        fields
      });
      return;
    }

    setIsPending(true);
    try {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false
      });

      if (result?.error) {
        try {
          const errorData = JSON.parse(result.error);
          setState({
            errorData,
            message: errorData.error?.message || 'Invalid credentials',
            errors: {
              email: errorData.error?.errors?.email || '',
              password: errorData.error?.errors?.password || 'Invalid credentials'
            },
            fields
          });
          return;
        } catch (error) {
          setState({
            message: result.error,
            errors: {
              email: '',
              password: result.error
            },
            fields
          });
          return;
        }
      }

      setState({
        message: 'success',
        errors: undefined,
        fields: {
          email: '',
          password: ''
        }
      });
      event.currentTarget.reset();
    } catch (error: any) {
      setState({
        message: 'wrong',
        errors: {
          email: '',
          password: error.message || 'Unexpected error occurred'
        },
        fields
      });
    } finally {
      setIsPending(false);
    }
  };

  return (
    <form
      className={style.form}
      onSubmit={handleSubmit}
    >
      <Input
        type='email'
        key={'email'}
        name='email'
        label='Email'
        placeholder='Wpisz swój email'
        defaultValue={state.fields.email}
        disabled={isPending}
      />
      <Input
        type='password'
        key={'password'}
        name='password'
        label='Hasło'
        placeholder='Podaj hasło'
        defaultValue={state.fields.password}
        disabled={isPending}
      />
      <Button
        type='submit'
        label='Zaloguj się'
        isLoading={isPending}
      />
    </form>
  );
};

export default LoginForm;
