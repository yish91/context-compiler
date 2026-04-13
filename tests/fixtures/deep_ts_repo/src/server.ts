import express from "express";
import { userRoutes } from "./routes/users";

const app = express();
app.use("/api", userRoutes);

export function bootstrap() {
  app.listen(3000);
}

bootstrap();
