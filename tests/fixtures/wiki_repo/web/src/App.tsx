import React from 'react';
import { Login } from './auth/Login';

interface AppProps {
  title: string;
}

export function App({ title }: AppProps): JSX.Element {
  const [isLoggedIn, setIsLoggedIn] = React.useState(false);

  if (!isLoggedIn) {
    return <Login onSuccess={() => setIsLoggedIn(true)} />;
  }

  return (
    <div className="app">
      <h1>{title}</h1>
      <main>Welcome to the wiki!</main>
    </div>
  );
}
