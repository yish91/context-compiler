type FooterProps = {
  year?: number;
};

export function Footer({ year = 2026 }: FooterProps) {
  return <footer>{year}</footer>;
}
