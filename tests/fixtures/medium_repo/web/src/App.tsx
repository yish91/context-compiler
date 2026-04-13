import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { fetchUsers, fetchItems } from "./api";

type AppState = {
  title: string;
  loading: boolean;
};

export function App() {
  const state: AppState = {
    title: process.env.APP_NAME ?? "Medium",
    loading: false,
  };

  return (
    <main>
      <Header title={state.title} />
      <section>
        <h2>Users</h2>
        <UserList />
      </section>
      <section>
        <h2>Items</h2>
        <ItemList />
      </section>
      <Footer />
    </main>
  );
}

function UserList() {
  const users = fetchUsers();
  return <pre>{JSON.stringify(users)}</pre>;
}

function ItemList() {
  const items = fetchItems();
  return <pre>{JSON.stringify(items)}</pre>;
}
