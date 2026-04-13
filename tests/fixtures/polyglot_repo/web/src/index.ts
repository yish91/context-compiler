import { router } from "./routes";
import { env } from "./config";
import { Card } from "./components/Card";

export function bootstrap(): string {
  return `${router()}-${env.APP_NAME}-${Card.name}`;
}
