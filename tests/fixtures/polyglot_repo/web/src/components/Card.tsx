type CardProps = {
  title: string;
};

export function Card({ title }: CardProps) {
  return <section>{title}</section>;
}
