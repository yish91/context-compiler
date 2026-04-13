import React from "react";

interface UserCardProps {
  user: string;
  onSelect: () => void;
}

export function UserCard({ user, onSelect }: UserCardProps) {
  return <div onClick={onSelect}>{user}</div>;
}
