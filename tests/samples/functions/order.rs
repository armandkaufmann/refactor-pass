use std::fmt;

pub struct Order<'a> {
    id: &'a str,
}

impl<'a> Order<'a> {
    pub fn new(id: &'a str) -> Self {
        Order { id }
    }

    pub async fn long_one<T: Into<String>>(
        &self,
        a: T,
    ) -> Result<(), Error>
    where
        T: Send,
    {
        let c = '}';
        Ok(())
    }
}

pub trait Named {
    fn name(&self) -> String;
}

impl fmt::Display for Order<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.id)
    }
}

fn main() {
    let add = |a: i32, b: i32| a + b;
    println!("{}", add(1, 2));
}
