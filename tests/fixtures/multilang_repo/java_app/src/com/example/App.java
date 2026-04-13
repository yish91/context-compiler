package com.example;

import java.util.List;
import java.util.Map;

public class App {
    public void bootstrap() {
        System.out.println("ok");
    }

    public List<String> users() {
        return List.of();
    }
}

class Settings {
    public Map<String, String> load() {
        return Map.of();
    }
}
