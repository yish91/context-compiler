import { Router } from "express";

const router = Router();

export function getUsers(req: any, res: any) {
  res.json([]);
}

router.get("/users", getUsers);

export const userRoutes = router;
