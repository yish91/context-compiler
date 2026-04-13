type HeaderProps = {
  title: string;
};

export function Header({ title }: HeaderProps) {
  return <header>{title}</header>;
}
