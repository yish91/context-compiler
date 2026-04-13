use std::collections::HashMap;
use std::io;

pub struct User {
    pub id: u32,
    pub email: String,
}

pub trait Greeter {
    fn greet(&self) -> String;
}

pub fn bootstrap() -> HashMap<u32, User> {
    HashMap::new()
}

pub fn shutdown() -> io::Result<()> {
    Ok(())
}
