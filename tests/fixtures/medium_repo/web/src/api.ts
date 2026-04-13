const BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function fetchUsers(): Promise<string[]> {
  const response = await fetch(`${BASE_URL}/users`);
  return response.json();
}

export async function fetchItems(): Promise<string[]> {
  const response = await fetch(`${BASE_URL}/items`);
  return response.json();
}
